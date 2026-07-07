import logging
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from production.tasks import (
    notify_production_stage_complete,
    notify_job_ready,
    notify_error_report_created,
)

logger = logging.getLogger(__name__)


class ProductionJobService:

    @staticmethod
    def create_for_order(order):
        from production.models import ProductionJob, ProductionTask, ProductStageConfig

        job = ProductionJob.objects.create(order=order)
        items = list(order.items.select_related("product").all())

        product_ids = [item.product_id for item in items]
        configs_by_product = {}
        for config in (
            ProductStageConfig.objects.filter(product_id__in=product_ids)
            .select_related("stage")
            .order_by("display_order")
        ):
            configs_by_product.setdefault(config.product_id, []).append(config)

        tasks = []
        for item in items:
            stage_configs = configs_by_product.get(item.product_id, [])
            if not stage_configs:
                logger.warning(
                    "Producto %s (id=%s) sin etapas configuradas — no se crean tasks",
                    item.product.name,
                    item.product_id,
                )
                continue
            for config in stage_configs:
                tasks.append(
                    ProductionTask(
                        job=job,
                        order_item=item,
                        stage=config.stage,
                        status=ProductionTask.Status.PENDING,
                    )
                )

        ProductionTask.objects.bulk_create(tasks)
        return job

    @staticmethod
    def complete_task(task, user, started_at, notes=""):
        from production.models import ProductionJob, ProductionTask
        from production.state import ProductionJobStateService

        # Un job pausado o cancelado no acepta avances.
        job_status = task.job.status
        if job_status in (ProductionJob.Status.PAUSED, ProductionJob.Status.CANCELLED):
            raise ValidationError(
                f"No se puede completar «{task.stage.name}»: "
                f"el job #{task.job_id} está {task.job.get_status_display().lower()}."
            )

        # Regla de Oro: no pasar a la siguiente etapa si la anterior está pendiente.
        blocked_by = (
            ProductionTask.objects.filter(
                job=task.job,
                order_item=task.order_item,
                stage__display_order__lt=task.stage.display_order,
                status=ProductionTask.Status.PENDING,
            )
            .select_related("stage")
            .order_by("-stage__display_order")
            .first()
        )
        if blocked_by:
            raise ValidationError(
                f"No se puede completar «{task.stage.name}»: "
                f"la etapa «{blocked_by.stage.name}» aún está pendiente."
            )

        with transaction.atomic():
            locked = (
                ProductionTask.objects.select_for_update()
                .filter(pk=task.pk, status=ProductionTask.Status.PENDING)
                .first()
            )
            if locked is None:
                logger.warning("Task %s already completed or does not exist", task.pk)
                return
            locked.status = ProductionTask.Status.COMPLETED
            locked.completed_by = user
            locked.completed_at = timezone.now()
            locked.started_at = started_at
            locked.notes = notes
            locked.save(
                update_fields=[
                    "status", "completed_by", "completed_at", "started_at", "notes"
                ]
            )

            job = ProductionJob.objects.select_for_update().get(pk=task.job_id)
            if job.status == ProductionJob.Status.PENDING:
                ProductionJobStateService.transition(
                    job, ProductionJob.Status.IN_PROGRESS
                )

            job_finished = not (
                ProductionTask.objects.filter(job=task.job_id)
                .exclude(status=ProductionTask.Status.COMPLETED)
                .exists()
            )
            if job_finished and job.status != ProductionJob.Status.COMPLETED:
                ProductionJobStateService.transition(
                    job, ProductionJob.Status.COMPLETED
                )

        try:
            notify_production_stage_complete.delay(task.pk)
        except Exception:
            logger.warning("Celery unavailable — skipping notify_production_stage_complete for task %s", task.pk)

        if job_finished:
            try:
                notify_job_ready.delay(task.job_id)
            except Exception:
                logger.warning("Celery unavailable — skipping notify_job_ready for job %s", task.job_id)

    @staticmethod
    def assign_task(task, operario):
        task.assigned_to = operario
        task.save(update_fields=["assigned_to"])
        if operario is not None:
            try:
                from production.tasks import notify_task_assigned
                notify_task_assigned.delay(task.pk)
            except Exception:
                logger.warning("Celery unavailable — skipping notify_task_assigned for task %s", task.pk)

    @staticmethod
    def toggle_urgent(job):
        job.is_urgent = not job.is_urgent
        job.save(update_fields=["is_urgent"])
        return job


class OperarioService:

    @staticmethod
    def create(*, username, password, first_name="", last_name="", email=""):
        from django.contrib.auth import get_user_model
        from accounts.models import Role

        User = get_user_model()
        if User.objects.filter(username=username).exists():
            raise ValueError(f"El usuario '{username}' ya existe.")

        op_role, _ = Role.objects.get_or_create(
            name="OPERARIO", defaults={"is_production_type": True}
        )
        user = User.objects.create_user(
            username=username,
            first_name=first_name,
            last_name=last_name,
            email=email,
            password=password,
        )
        user.profile_completed = True
        user.save(update_fields=["profile_completed"])
        user.roles.add(op_role)
        return user

    @staticmethod
    def assign_existing(user):
        """Agrega el rol OPERARIO a un usuario ya registrado en el sistema.

        No modifica contraseña ni datos del usuario. Levanta ValueError si ya
        tiene el rol OPERARIO.
        """
        from accounts.models import Role

        op_role, _ = Role.objects.get_or_create(
            name="OPERARIO", defaults={"is_production_type": True}
        )
        if user.roles.filter(pk=op_role.pk).exists():
            raise ValueError(f"'{user.username}' ya es operario.")

        user.profile_completed = True
        user.save(update_fields=["profile_completed"])
        user.roles.add(op_role)
        return user

    @staticmethod
    def assign_role(operario, prod_role, assigned_by):
        from production.models import OperarioRoleAssignment

        OperarioRoleAssignment.objects.get_or_create(
            user=operario,
            role=prod_role,
            defaults={"assigned_by": assigned_by},
        )

    @staticmethod
    def remove_role(operario, prod_role):
        from production.models import OperarioRoleAssignment

        OperarioRoleAssignment.objects.filter(user=operario, role=prod_role).delete()


class ErrorReportService:

    @staticmethod
    def create(
        *,
        reported_by,
        description,
        error_types,
        order=None,
        job=None,
        stage=None,
        area="",
        error_type_other="",
        responsible=None,
        responsible_area="",
        error_causes=None,
        cause_other="",
        cause_detail="",
        error_impacts=None,
        impact_other="",
        impact_description="",
        corrective_actions="",
        prevention_actions="",
    ):
        from production.models import ErrorReport

        report = ErrorReport.objects.create(
            reported_by=reported_by,
            description=description,
            error_types=error_types or [],
            order=order,
            job=job,
            stage=stage,
            area=area,
            error_type_other=error_type_other,
            responsible=responsible,
            responsible_area=responsible_area,
            error_causes=error_causes or [],
            cause_other=cause_other,
            cause_detail=cause_detail,
            error_impacts=error_impacts or [],
            impact_other=impact_other,
            impact_description=impact_description,
            corrective_actions=corrective_actions,
            prevention_actions=prevention_actions,
            requires_reposition=False,
        )
        # Auto-flag reposition if error type warrants it
        if report.is_reposition_type:
            report.requires_reposition = True
            report.save(update_fields=["requires_reposition"])

        logger.info(
            "ErrorReport #%s creado por user=%s (reposicion=%s)",
            report.pk,
            reported_by,
            report.requires_reposition,
        )

        try:
            notify_error_report_created.delay(report.pk)
        except Exception:
            logger.warning(
                "Celery unavailable — skipping notify_error_report_created for report %s",
                report.pk,
            )

        return report

    @staticmethod
    def review(report, reviewed_by, review_status, review_notes="", is_exception=False, exception_reason=""):
        from production.models import ErrorReport

        report.review_status = review_status
        report.reviewed_by = reviewed_by
        report.reviewed_at = timezone.now()
        report.review_notes = review_notes
        report.is_exception = is_exception
        report.exception_reason = exception_reason
        if review_status == ErrorReport.ReviewStatus.EXCEPTION_GRANTED:
            report.requires_reposition = False
            report.is_exception = True
        report.save(
            update_fields=[
                "review_status", "reviewed_by", "reviewed_at",
                "review_notes", "is_exception", "exception_reason", "requires_reposition",
            ]
        )
        return report

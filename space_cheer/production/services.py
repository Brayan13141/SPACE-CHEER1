import logging
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from production.tasks import notify_production_stage_complete

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
        from production.models import ProductionTask

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

        notify_production_stage_complete.delay(task.pk)

    @staticmethod
    def assign_task(task, operario):
        task.assigned_to = operario
        task.save(update_fields=["assigned_to"])

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

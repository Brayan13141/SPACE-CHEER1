import logging
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
            locked.save(update_fields=["status", "completed_by", "completed_at", "started_at", "notes"])

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
        """Crea un usuario OPERARIO con perfil completo.

        Levanta ValueError si el username ya existe.
        """
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
        """Asigna un ProductionRole al operario (idempotente)."""
        from production.models import OperarioRoleAssignment

        OperarioRoleAssignment.objects.get_or_create(
            user=operario,
            role=prod_role,
            defaults={"assigned_by": assigned_by},
        )

    @staticmethod
    def remove_role(operario, prod_role):
        """Quita un ProductionRole del operario."""
        from production.models import OperarioRoleAssignment

        OperarioRoleAssignment.objects.filter(user=operario, role=prod_role).delete()

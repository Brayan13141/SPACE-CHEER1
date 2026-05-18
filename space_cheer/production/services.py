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

        tasks = []
        for item in order.items.select_related("product").all():
            stage_configs = ProductStageConfig.objects.filter(
                product=item.product
            ).select_related("stage").order_by("display_order")

            if not stage_configs.exists():
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
                        status="PENDING",
                        started_at=job.created_at,
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
                .filter(pk=task.pk, status="PENDING")
                .first()
            )
            if locked is None:
                logger.warning("Task %s already completed or does not exist", task.pk)
                return
            locked.status = "COMPLETED"
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

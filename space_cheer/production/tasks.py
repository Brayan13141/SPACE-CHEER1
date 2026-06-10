import logging
from celery import shared_task
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)
User = get_user_model()


@shared_task(bind=True, max_retries=3, acks_late=True)
def notify_production_stage_complete(self, task_id):
    from production.models import ProductionTask
    from orders.services.notifications.order_notifications import OrderNotificationService

    try:
        task = ProductionTask.objects.select_related(
            "job__order", "order_item__product", "stage", "completed_by"
        ).get(pk=task_id)
    except ProductionTask.DoesNotExist:
        logger.warning("ProductionTask %s no encontrada para notificación", task_id)
        return

    admins_and_staff = list(
        User.objects.filter(roles__name__in=["ADMIN", "STAFF"], is_active=True).distinct()
    )

    try:
        OrderNotificationService.notify_production_task_completed(task, admins_and_staff)
    except Exception as exc:
        logger.exception("Error al notificar sobre task %s: %s", task_id, exc)

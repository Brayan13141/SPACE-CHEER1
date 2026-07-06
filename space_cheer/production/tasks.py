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

    admins = list(
        User.objects.filter(roles__name="ADMIN", is_active=True).distinct()
    )

    try:
        OrderNotificationService.notify_production_task_completed(task, admins)
    except Exception as exc:
        logger.exception("Error al notificar sobre task %s: %s", task_id, exc)


@shared_task(bind=True, max_retries=3, acks_late=True)
def notify_task_assigned(self, task_id):
    """Notifica al operario asignado a una ProductionTask."""
    from production.models import ProductionTask
    from accounts.models import Notification
    from django.core.mail import send_mail
    from django.conf import settings

    try:
        task = ProductionTask.objects.select_related(
            "job__order", "order_item__product", "stage", "assigned_to"
        ).get(pk=task_id)
    except ProductionTask.DoesNotExist:
        logger.warning("ProductionTask %s no encontrada para notificación de asignación", task_id)
        return

    if task.assigned_to is None:
        logger.warning("ProductionTask %s no tiene operario asignado, se omite notificación", task_id)
        return

    operario = task.assigned_to
    order = task.job.order
    product_name = task.order_item.product.name if task.order_item_id else "N/A"

    # 1. Crear notificación en BD
    Notification.objects.create(
        user=operario,
        title=f"Nueva tarea asignada: {task.stage.name}",
        body=(
            f"Se te ha asignado la tarea '{task.stage.name}' "
            f"para la orden #{order.id} ({product_name})"
        ),
        notification_type=Notification.NotificationType.TASK_ASSIGNED,
    )

    # 2. Enviar email (fallo silencioso para no bloquear la notificación en BD)
    if operario.email:
        try:
            send_mail(
                subject="Space Cheer — Nueva tarea asignada",
                message=(
                    f"Hola {operario.get_full_name() or operario.username},\n\n"
                    f"Se te ha asignado la tarea '{task.stage.name}' "
                    f"para la orden #{order.id} ({product_name}).\n\n"
                    f"Ingresa al dashboard de producción para ver los detalles."
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[operario.email],
                fail_silently=False,
            )
        except Exception as exc:
            logger.exception(
                "Error enviando email de asignación de task %s: %s", task_id, exc
            )


@shared_task(bind=True, max_retries=3, acks_late=True)
def notify_job_ready(self, job_id):
    """Notifica a ADMIN cuando todas las tasks de un ProductionJob quedaron completadas."""
    from production.models import ProductionJob
    from accounts.models import Notification

    try:
        job = ProductionJob.objects.select_related("order").get(pk=job_id)
    except ProductionJob.DoesNotExist:
        logger.warning("ProductionJob %s no encontrado para notificación de job listo", job_id)
        return

    admins = User.objects.filter(roles__name="ADMIN", is_active=True).distinct()

    Notification.objects.bulk_create([
        Notification(
            user=admin,
            title=f"Job de producción #{job.pk} listo",
            body=f"Todas las tareas de la orden #{job.order_id} están completadas — lista para entregar.",
            notification_type=Notification.NotificationType.JOB_READY,
        )
        for admin in admins
    ])


@shared_task(bind=True, max_retries=3, acks_late=True)
def notify_error_report_created(self, report_id):
    """Notifica a ADMIN cuando se crea un ErrorReport."""
    from production.models import ErrorReport
    from accounts.models import Notification

    try:
        report = ErrorReport.objects.select_related("order", "stage").get(pk=report_id)
    except ErrorReport.DoesNotExist:
        logger.warning("ErrorReport %s no encontrado para notificación", report_id)
        return

    admins = User.objects.filter(roles__name="ADMIN", is_active=True).distinct()
    stage_name = report.stage.name if report.stage_id else "sin etapa"
    reposition_note = " ⚠️ Requiere reposición." if report.requires_reposition else ""

    Notification.objects.bulk_create([
        Notification(
            user=admin,
            title=f"Nuevo reporte de error #{report.pk}",
            body=f"Etapa: {stage_name}.{reposition_note}",
            notification_type=Notification.NotificationType.ERROR_REPORTED,
        )
        for admin in admins
    ])

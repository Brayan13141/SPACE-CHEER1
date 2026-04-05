# orders/tasks.py

from celery import shared_task
from django.utils import timezone
from django.db import transaction
from orders.models import Order, OrderLog
from orders.services.measurements.MeasurementLifecycleService import (
    MeasurementLifecycleService,
)
import logging

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name="orders.tasks.auto_close_measurements",
    max_retries=3,
    default_retry_delay=300,
    autoretry_for=(Exception,),
    retry_backoff=True,
    acks_late=True,  # ← Importante para reliability
)
def auto_close_measurements(self, *args, **kwargs):
    """
    Cierra automáticamente medidas vencidas.

    Se ejecuta diariamente a las 00:05 AM.
    """
    logger.info("🔄 [TASK] Iniciando cierre automático de medidas")

    today = timezone.now().date()

    # Query SIN lock primero (lectura rápida)
    candidates = Order.objects.filter(
        measurements_locked=False,
        measurements_due_date__isnull=False,
        measurements_due_date__lte=today,
    ).values_list("id", flat=True)

    order_ids = list(candidates)
    total = len(order_ids)

    logger.info(f"📊 [TASK] {total} órdenes candidatas para cierre")

    if not total:
        return {
            "total_candidates": 0,
            "successfully_closed": 0,
            "failed": 0,
            "skipped": 0,
            "errors": [],
            "execution_time": timezone.now().isoformat(),
        }

    results = {"closed": 0, "failed": 0, "skipped": 0, "errors": []}

    # procesar una por una CON lock
    for order_id in order_ids:
        try:
            with transaction.atomic():
                #  Adquirir lock DENTRO de la transacción
                order = Order.objects.select_for_update(nowait=True).get(id=order_id)

                # Doble verificación (puede haber cambiado)
                if not order.measurements_open or order.measurements_locked:
                    logger.warning(
                        f"  [TASK] Orden #{order_id} ya procesada (race condition)"
                    )
                    results["skipped"] += 1
                    continue

                if not order.measurements_due_date:
                    logger.warning(f"  [TASK] Orden #{order_id} sin fecha límite")
                    results["skipped"] += 1
                    continue

                # Verificar que realmente está vencida
                if order.measurements_due_date > today:
                    logger.warning(f"  [TASK] Orden #{order_id} no vencida todavía")
                    results["skipped"] += 1
                    continue

                #  Cerrar medidas
                MeasurementLifecycleService.auto_close_if_due(order)

                # Auditoría
                OrderLog.objects.create(
                    order=order,
                    user=None,
                    action="MEASUREMENTS_AUTO_CLOSED",
                    from_status=order.status,
                    to_status=order.status,
                    notes=f"Cerrado automáticamente (vencida: {order.measurements_due_date})",
                    metadata={
                        "task_id": self.request.id,
                        "due_date": str(order.measurements_due_date),
                        "closed_on": str(today),
                    },
                )

                results["closed"] += 1
                logger.info(f" [TASK] Orden #{order_id} cerrada exitosamente")

        except Order.DoesNotExist:
            logger.warning(f" [TASK] Orden #{order_id} no existe")
            results["skipped"] += 1

        except Exception as e:
            results["failed"] += 1
            results["errors"].append(
                {
                    "order_id": order_id,
                    "error": str(e),
                }
            )
            logger.exception(f" [TASK] Error procesando orden #{order_id}")

    # Resultado final
    summary = {
        "total_candidates": total,
        "successfully_closed": results["closed"],
        "failed": results["failed"],
        "skipped": results["skipped"],
        "errors": results["errors"],
        "execution_time": timezone.now().isoformat(),
    }

    if results["failed"]:
        logger.error(
            f"  [TASK] Completado con {results['failed']} errores: "
            f"{results['errors']}"
        )
    else:
        logger.info(f" [TASK] Completado: {results['closed']}/{total} cerradas")

    return summary

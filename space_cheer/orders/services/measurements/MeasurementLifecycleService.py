# orders/services/measurement_lifecycle.py

from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ValidationError
from orders.models import Order


class MeasurementLifecycleService:
    """
    Maneja el ciclo de vida de edición de medidas:
    - abrir
    - cerrar
    - bloqueo definitivo
    """

    # ==========================
    # AUTO LOGIC
    # ==========================

    @staticmethod
    def auto_close_if_due(order: Order):
        """
        Cierra automáticamente si se alcanzó la fecha límite.
        Ideal para cron / celery beat.
        """
        if order.measurements_locked:
            return

        if not order.measurements_due_date:
            return

        if timezone.now().date() >= order.measurements_due_date:
            if order.measurements_open:
                order.measurements_open = False
                order.save(update_fields=["measurements_open"])

    # ==========================
    # MANUAL ACTIONS
    # ==========================

    @staticmethod
    @transaction.atomic
    def open(order: Order, user=None):
        """
        Abre edición de medidas
        """
        if order.measurements_locked:
            raise ValidationError("Las medidas están bloqueadas definitivamente")

        if not order.can_edit_general():
            raise ValidationError("La orden no permite edición en este estado")

        if order.measurements_open:
            return  # idempotente

        order.measurements_open = True
        order.save(update_fields=["measurements_open"])

    @staticmethod
    @transaction.atomic
    def close(order: Order, user=None):
        """
        Cierre manual (temporal)
        """
        if order.measurements_locked:
            return

        if not order.measurements_open:
            return  # idempotente

        order.measurements_open = False
        order.save(update_fields=["measurements_open"])

    @staticmethod
    @transaction.atomic
    def reopen(order: Order, user=None):
        """
        Reabrir medidas (solo si no están bloqueadas)
        """
        if order.status not in ["DRAFT", "PENDING", "DESIGN_APPROVED"]:
            raise ValidationError("No se pueden reabrir medidas en este estado")

        if order.measurements_locked:
            raise ValidationError("No puedes reabrir medidas bloqueadas")

        if not order.can_edit_general():
            raise ValidationError("La orden no permite reabrir medidas en este estado")

        order.measurements_open = True
        order.save(update_fields=["measurements_open"])

    # ==========================
    # FINAL LOCK
    # ==========================

    @staticmethod
    @transaction.atomic
    def lock(order: Order, user=None):
        """
        Bloqueo definitivo (ej: cuando se aprueba diseño)
        """
        if order.measurements_locked:
            return

        # regla crítica: no deberías bloquear si faltan medidas
        # Order.validate_order_ready(order)

        order.measurements_locked = True
        order.measurements_open = False
        order.locked_at = timezone.now()

        order.save(
            update_fields=[
                "measurements_locked",
                "measurements_open",
                "locked_at",
            ]
        )

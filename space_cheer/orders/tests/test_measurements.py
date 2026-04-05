from django.test import TestCase
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta

from orders.tests.factories import (
    OrderFactory,
    TeamOrderFactory,
    OrderItemFactory,
    OrderItemAthleteFactory,
    ProductWithMeasurementsFactory,
    AthleteFactory,
    TeamFactory,
    UserTeamMembershipFactory,
    MeasurementFieldFactory,
)
from orders.services.measurements.MeasurementLifecycleService import (
    MeasurementLifecycleService,
)


class MeasurementLifecycleTests(TestCase):
    """Tests para el ciclo de vida de medidas"""

    def test_measurements_start_open(self):
        """Las medidas inician abiertas por defecto"""
        order = OrderFactory()

        self.assertTrue(order.measurements_open)
        self.assertFalse(order.measurements_locked)

    def test_close_measurements(self):
        """Cerrar medidas manualmente"""
        order = OrderFactory(measurements_open=True)

        MeasurementLifecycleService.close(order)

        order.refresh_from_db()
        self.assertFalse(order.measurements_open)
        self.assertFalse(order.measurements_locked)

    def test_close_measurements_idempotent(self):
        """Cerrar medidas múltiples veces no causa error"""
        order = OrderFactory(measurements_open=True)

        MeasurementLifecycleService.close(order)
        MeasurementLifecycleService.close(order)  # Segunda vez

        order.refresh_from_db()
        self.assertFalse(order.measurements_open)

    def test_reopen_measurements(self):
        """Reabrir medidas cerradas"""
        order = OrderFactory(
            status="DRAFT", measurements_open=False, measurements_locked=False
        )

        MeasurementLifecycleService.reopen(order)

        order.refresh_from_db()
        self.assertTrue(order.measurements_open)

    def test_cannot_reopen_locked_measurements(self):
        """No se pueden reabrir medidas bloqueadas"""
        order = OrderFactory(measurements_open=False, measurements_locked=True)

        with self.assertRaises(ValidationError):
            MeasurementLifecycleService.reopen(order)

    def test_lock_measurements(self):
        """Bloquear medidas definitivamente"""
        order = OrderFactory(measurements_open=True, measurements_locked=False)

        MeasurementLifecycleService.lock(order)

        order.refresh_from_db()
        self.assertTrue(order.measurements_locked)
        self.assertFalse(order.measurements_open)
        self.assertIsNotNone(order.locked_at)

    def test_lock_measurements_idempotent(self):
        """Bloquear múltiples veces no causa error"""
        order = OrderFactory()

        MeasurementLifecycleService.lock(order)
        MeasurementLifecycleService.lock(order)  # Segunda vez

        order.refresh_from_db()
        self.assertTrue(order.measurements_locked)

    def test_auto_close_if_due_not_due_yet(self):
        """No cierra si no ha llegado la fecha"""
        future_date = timezone.now().date() + timedelta(days=5)
        order = OrderFactory(
            measurements_due_date=future_date,
            measurements_open=True,
            measurements_locked=False,
        )

        MeasurementLifecycleService.auto_close_if_due(order)

        order.refresh_from_db()
        self.assertTrue(order.measurements_open)

    def test_auto_close_if_due_date_reached(self):
        """Cierra automáticamente cuando llega la fecha"""
        past_date = timezone.now().date() - timedelta(days=1)
        order = OrderFactory(
            measurements_due_date=past_date,
            measurements_open=True,
            measurements_locked=False,
        )

        MeasurementLifecycleService.auto_close_if_due(order)

        order.refresh_from_db()
        self.assertFalse(order.measurements_open)

    def test_auto_close_respects_lock(self):
        """No cierra si ya está bloqueado"""
        past_date = timezone.now().date() - timedelta(days=1)
        order = OrderFactory(
            measurements_due_date=past_date,
            measurements_open=True,
            measurements_locked=True,
        )

        MeasurementLifecycleService.auto_close_if_due(order)

        order.refresh_from_db()
        self.assertTrue(order.measurements_open)  # No cambió

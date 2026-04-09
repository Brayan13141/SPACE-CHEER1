# orders/tests/test_tasks.py

import pytest
from datetime import date, timedelta
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.utils import timezone

from orders.models import Order, OrderLog
from orders.tasks import auto_close_measurements
from orders.tests.factories import (
    CoachFactory,
    OrderFactory,
)


def make_overdue_order(coach=None):
    """Helper: crea orden con medidas vencidas."""
    if coach is None:
        coach = CoachFactory()
    order = OrderFactory(
        created_by=coach,
        owner_user=coach,
        measurements_locked=False,
    )
    order.measurements_due_date = date.today() - timedelta(days=1)
    order.save(update_fields=["measurements_due_date"])
    return order


def make_future_order(coach=None):
    """Helper: crea orden con medidas aún vigentes."""
    if coach is None:
        coach = CoachFactory()
    order = OrderFactory(
        created_by=coach,
        owner_user=coach,
        measurements_open=True,
        measurements_locked=False,
    )
    order.measurements_due_date = date.today() + timedelta(days=5)
    order.save(update_fields=["measurements_due_date"])
    return order


# ===========================================================
# TASK: auto_close_measurements
# ===========================================================


@pytest.mark.django_db
class AutoCloseMeasurementsTaskTests(TestCase):

    def _run_task(self):
        """
        Ejecuta la task sin Celery (directo).
        El `self` de @bind es un mock.
        """
        mock_self = MagicMock()
        mock_self.request.id = "test-task-id"
        return auto_close_measurements(mock_self)

    # ----------------------------------------------------------
    # Casos básicos
    # ----------------------------------------------------------

    def test_closes_overdue_orders(self):
        order = make_overdue_order()
        self._run_task()
        order.refresh_from_db()
        self.assertFalse(order.measurements_open)

    def test_does_not_close_future_orders(self):
        order = make_future_order()
        self._run_task()
        order.refresh_from_db()
        self.assertTrue(order.measurements_open)

    def test_does_not_close_locked_orders(self):
        coach = CoachFactory()
        order = OrderFactory(
            created_by=coach,
            owner_user=coach,
            measurements_open=True,
            measurements_locked=True,
        )
        order.measurements_due_date = date.today() - timedelta(days=1)
        order.save(update_fields=["measurements_due_date", "measurements_locked"])

        self._run_task()
        order.refresh_from_db()
        # measurements_locked=True → no debe modificarse
        self.assertTrue(order.measurements_open)

    def test_does_not_close_already_closed_measurements(self):
        coach = CoachFactory()
        order = OrderFactory(
            created_by=coach,
            owner_user=coach,
            measurements_open=False,
            measurements_locked=False,
        )
        order.measurements_due_date = date.today() - timedelta(days=1)
        order.save(update_fields=["measurements_due_date"])

        self._run_task()
        order.refresh_from_db()
        self.assertFalse(order.measurements_open)  # ya estaba cerrado

    def test_does_not_close_orders_without_due_date(self):
        coach = CoachFactory()
        order = OrderFactory(
            created_by=coach,
            owner_user=coach,
            measurements_open=True,
            measurements_locked=False,
        )
        # Sin measurements_due_date
        self.assertIsNone(order.measurements_due_date)

        self._run_task()
        order.refresh_from_db()
        self.assertTrue(order.measurements_open)  # no se tocó

    # ----------------------------------------------------------
    # Resultado / resumen
    # ----------------------------------------------------------

    def test_returns_summary_dict(self):
        result = self._run_task()
        self.assertIn("total_candidates", result)
        self.assertIn("successfully_closed", result)
        self.assertIn("failed", result)
        self.assertIn("skipped", result)

    def test_empty_queryset_returns_zero_counts(self):
        # Sin órdenes vencidas
        result = self._run_task()
        self.assertEqual(result["total_candidates"], 0)
        self.assertEqual(result["successfully_closed"], 0)

    def test_closed_count_matches_orders_processed(self):
        coach = CoachFactory()
        order1 = make_overdue_order(coach)
        order2 = make_overdue_order(coach)

        result = self._run_task()
        self.assertEqual(result["successfully_closed"], 2)

    def test_creates_audit_log(self):
        order = make_overdue_order()
        self._run_task()

        log = OrderLog.objects.filter(
            order=order,
            action="MEASUREMENTS_AUTO_CLOSED",
        ).first()
        self.assertIsNotNone(log)
        self.assertIsNone(log.user)  # task no tiene usuario

    def test_audit_log_metadata_has_task_id(self):
        order = make_overdue_order()
        self._run_task()

        log = OrderLog.objects.filter(
            order=order,
            action="MEASUREMENTS_AUTO_CLOSED",
        ).first()
        self.assertIn("task_id", log.metadata)
        self.assertIn("due_date", log.metadata)

    # ----------------------------------------------------------
    # Robustez / edge cases
    # ----------------------------------------------------------

    def test_handles_empty_database_without_crash(self):
        try:
            result = self._run_task()
        except Exception as e:
            self.fail(f"Task falló con BD vacía: {e}")

    def test_processes_multiple_orders_independently(self):
        """Si una orden falla, las demás se procesan."""
        coach = CoachFactory()
        order1 = make_overdue_order(coach)
        order2 = make_overdue_order(coach)

        # Ambas deben cerrarse
        result = self._run_task()
        order1.refresh_from_db()
        order2.refresh_from_db()

        self.assertFalse(order1.measurements_open)
        self.assertFalse(order2.measurements_open)

    def test_skips_order_already_processed(self):
        """
        Race condition: orden que se cierra entre el SELECT y el lock.
        La task debe contarla como 'skipped' no como error.
        """
        coach = CoachFactory()
        order = OrderFactory(
            created_by=coach,
            owner_user=coach,
            measurements_open=True,
            measurements_locked=False,
        )
        order.measurements_due_date = date.today() - timedelta(days=1)
        order.save(update_fields=["measurements_due_date"])

        # Simular que ya fue cerrada antes del lock
        Order.objects.filter(pk=order.pk).update(measurements_open=False)

        result = self._run_task()
        self.assertEqual(result["skipped"], 1)
        self.assertEqual(result["successfully_closed"], 0)

    def test_today_due_date_closes_measurements(self):
        """Fecha de hoy = vencida (measurements_due_date__lte=today)."""
        coach = CoachFactory()
        order = OrderFactory(
            created_by=coach,
            owner_user=coach,
            measurements_open=True,
            measurements_locked=False,
        )
        order.measurements_due_date = date.today()
        order.save(update_fields=["measurements_due_date"])

        self._run_task()
        order.refresh_from_db()
        self.assertFalse(order.measurements_open)

    def test_task_failed_count_on_exception(self):
        """
        Verifica que el campo 'failed' se incrementa si hay un error
        inesperado al procesar una orden.
        """
        order = make_overdue_order()

        # Forzar una excepción en MeasurementLifecycleService
        with patch(
            "orders.tasks.MeasurementLifecycleService.auto_close_if_due",
            side_effect=RuntimeError("Error simulado"),
        ):
            result = self._run_task()

        self.assertGreater(result["failed"], 0)
        self.assertGreater(len(result["errors"]), 0)
        self.assertEqual(result["errors"][0]["order_id"], order.id)

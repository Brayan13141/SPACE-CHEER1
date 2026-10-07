"""
Bugs 6 y 9 de la verificación del 2026-10-04:

- Un pedido cancelado no acepta abonos.
- El cierre automático de medidas usa la fecha de México: antes cerraba un
  día antes a partir de las 18:00, cuando en UTC ya es el día siguiente.
"""

import datetime
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase

from orders.models import Order, OrderPayment
from orders.services.measurements.MeasurementLifecycleService import (
    MeasurementLifecycleService,
)
from orders.services.offline import OfflineOrderService
from orders.tests.factories import OfflineOrderFactory, OrderFactory, UserFactory


class CancelledOrderPaymentTests(TestCase):
    def setUp(self):
        self.admin = UserFactory(is_superuser=True)
        self.order = OfflineOrderFactory(agreed_price=Decimal("1000.00"))
        self.order.status = "CANCELLED"
        self.order.closed = True
        self.order._allow_status_change = True
        self.order.save()

    def test_pedido_cancelado_no_acepta_abonos(self):
        with self.assertRaises(ValidationError):
            OfflineOrderService.add_payment(
                order=self.order, admin_user=self.admin, amount="500",
            )
        self.assertFalse(OrderPayment.objects.filter(order=self.order).exists())

    def test_pedido_vivo_si_acepta_abonos(self):
        vivo = OfflineOrderFactory(agreed_price=Decimal("1000.00"))
        OfflineOrderService.add_payment(order=vivo, admin_user=self.admin, amount="500")
        self.assertEqual(vivo.total_paid, Decimal("500"))


class MeasurementsDueDateIsLocalTests(TestCase):
    def _order(self, due):
        order = OrderFactory(measurements_open=True)
        order.measurements_due_date = due
        order.save(update_fields=["measurements_due_date"])
        return order

    def test_no_cierra_medidas_un_dia_antes_por_la_noche(self):
        # 01:00 UTC del día 5 = 19:00 del día 4 en Ciudad de México:
        # la fecha límite es el 5 y todavía no llega.
        order = self._order(datetime.date(2026, 10, 5))
        utc_now = datetime.datetime(2026, 10, 5, 1, 0, tzinfo=datetime.timezone.utc)
        with patch("django.utils.timezone.now", return_value=utc_now):
            MeasurementLifecycleService.auto_close_if_due(order)
        self.assertTrue(Order.objects.get(pk=order.pk).measurements_open)

    def test_cierra_medidas_al_llegar_la_fecha_en_mexico(self):
        order = self._order(datetime.date(2026, 10, 5))
        utc_now = datetime.datetime(2026, 10, 5, 7, 0, tzinfo=datetime.timezone.utc)
        with patch("django.utils.timezone.now", return_value=utc_now):
            MeasurementLifecycleService.auto_close_if_due(order)
        self.assertFalse(Order.objects.get(pk=order.pk).measurements_open)

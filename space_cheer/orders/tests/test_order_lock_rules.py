"""
Reglas de cierre del pedido, halladas en la verificación del 2026-10-04:

- Un pedido con diseño no puede ir a producción sin que alguien apruebe el
  diseño: la UI ocultaba PENDING → IN_PRODUCTION, pero el backend lo dejaba.
- Los productos se cierran cuando el pedido se envía (decisión de Bryan): ya
  no se agregan ni se quitan desde PENDING. Tallas y medidas siguen sus
  propias reglas y no entran aquí.
"""

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from orders.models import Order
from orders.services.servicesItems.order_item_service import OrderItemService
from orders.services.state import OrderStateService
from orders.tests.factories import (
    CoachFactory,
    OrderDesignImageFactory,
    OrderFactory,
    OrderItemFactory,
    ProductFactory,
    UserFactory,
)
from orders.views.item_views import _can_user_delete_item


def _set_status(order, status):
    order.status = status
    order._allow_status_change = True
    order.save()
    return Order.objects.get(pk=order.pk)


class DesignApprovalRequiredForProductionTests(TestCase):
    def setUp(self):
        self.admin = UserFactory(is_superuser=True)
        self.order = OrderFactory()
        today = timezone.now().date()
        self.order.measurements_locked = True
        self.order.locked_at = timezone.now()
        self.order.measurements_due_date = today
        self.order.uniform_delivery_date = today
        self.order.first_payment_date = timezone.now()
        self.order.save()

    def test_pedido_con_diseno_no_salta_de_pending_a_produccion(self):
        OrderItemFactory(order=self.order, product=ProductFactory(usage_type="TEAM_CUSTOM"))
        OrderDesignImageFactory(order=self.order, is_final=True)
        order = _set_status(self.order, "PENDING")

        with self.assertRaisesMessage(ValidationError, "aprobarse el diseño"):
            OrderStateService.transition(order=order, to_status="IN_PRODUCTION", user=self.admin)

        self.assertEqual(Order.objects.get(pk=order.pk).status, "PENDING")

    def test_pedido_sin_diseno_si_va_de_pending_a_produccion(self):
        OrderItemFactory(order=self.order, product=ProductFactory())
        order = _set_status(self.order, "PENDING")

        order = OrderStateService.transition(order=order, to_status="IN_PRODUCTION", user=self.admin)

        self.assertEqual(order.status, "IN_PRODUCTION")


class ProductsLockedOnceSubmittedTests(TestCase):
    def setUp(self):
        self.creator = CoachFactory()
        self.order = OrderFactory(created_by=self.creator, owner_user=self.creator)
        self.item = OrderItemFactory(order=self.order, product=ProductFactory())
        self.extra = ProductFactory()

    def test_en_borrador_se_agregan_productos(self):
        OrderItemService.add_product(self.order, self.extra, quantity=1)
        self.assertEqual(self.order.items.count(), 2)

    def test_enviado_no_se_agregan_productos(self):
        order = _set_status(self.order, "PENDING")
        with self.assertRaises(ValidationError):
            OrderItemService.add_product(order, self.extra, quantity=1)
        self.assertEqual(order.items.count(), 1)

    def test_con_diseno_aprobado_no_se_agregan_productos(self):
        order = _set_status(self.order, "DESIGN_APPROVED")
        with self.assertRaises(ValidationError):
            OrderItemService.add_product(order, self.extra, quantity=1)

    def test_enviado_nadie_quita_productos(self):
        order = _set_status(self.order, "PENDING")
        admin = UserFactory(is_superuser=True)
        self.assertFalse(_can_user_delete_item(self.creator, order, self.item))
        self.assertFalse(_can_user_delete_item(admin, order, self.item))

    def test_vista_no_agrega_producto_a_pedido_enviado(self):
        order = _set_status(self.order, "PENDING")
        self.client.force_login(self.creator)

        self.client.post(
            reverse("orders:add_item_product_order", args=[order.pk]),
            {"product_id": self.extra.pk, "quantity": 1},
        )

        self.assertEqual(order.items.count(), 1)

    def test_vista_no_borra_producto_de_pedido_enviado(self):
        order = _set_status(self.order, "PENDING")
        self.client.force_login(self.creator)

        self.client.post(reverse("orders:order_item_delete", args=[self.item.pk]))

        self.assertTrue(order.items.filter(pk=self.item.pk).exists())

    def test_detalle_de_pedido_enviado_no_ofrece_agregar_producto(self):
        order = _set_status(self.order, "PENDING")
        self.client.force_login(self.creator)

        response = self.client.get(reverse("orders:detail_order", args=[order.pk]))

        self.assertEqual(response.status_code, 200)
        add_url = reverse("orders:add_item_product_order", args=[order.pk])
        self.assertNotContains(response, f'href="{add_url}"')
        delete_url = reverse("orders:order_item_delete", args=[self.item.pk])
        self.assertNotContains(response, f'data-delete-url="{delete_url}"')

"""Tests de vistas de pedidos offline (permisos + flujo de captura)."""
from decimal import Decimal

import pytest
from django.test import TestCase
from django.urls import reverse

from orders.models import Order
from orders.tests.factories import (
    CustomerFactory,
    ProductFactory,
    RoleFactory,
    SeasonFactory,
    UserFactory,
)


def _admin():
    # profile_completed=True es necesario: role_required redirige a onboarding
    # antes de validar roles si el perfil no está completo (ver test_views_admin.py).
    return UserFactory(
        is_staff=True, profile_completed=True, roles=[RoleFactory(name="ADMIN")]
    )


def _internal_product(**kw):
    kw.setdefault("scope", "INTERNAL")
    kw.setdefault("usage_type", "GLOBAL")
    kw.setdefault("size_strategy", "NONE")
    return ProductFactory(**kw)


class OfflineViewsPermissionTests(TestCase):
    def test_captura_requiere_admin(self):
        coach = UserFactory(roles=[RoleFactory(name="COACH")])
        self.client.force_login(coach)
        resp = self.client.get(reverse("orders:offline_order_create"))
        self.assertEqual(resp.status_code, 302)  # role_required redirige

    def test_captura_ok_para_admin(self):
        self.client.force_login(_admin())
        resp = self.client.get(reverse("orders:offline_order_create"))
        self.assertEqual(resp.status_code, 200)

    def test_clientes_requiere_admin(self):
        coach = UserFactory(roles=[RoleFactory(name="COACH")])
        self.client.force_login(coach)
        resp = self.client.get(reverse("orders:customer_list"))
        self.assertEqual(resp.status_code, 302)


class OfflineCaptureFlowTests(TestCase):
    def setUp(self):
        self.admin = _admin()
        self.client.force_login(self.admin)
        # Requerido por OfflineOrderService._resolve_product para crear
        # productos "al vuelo" (ver OfflineOrderServiceTests.setUp).
        self.season = SeasonFactory(is_active=True)

    def test_post_crea_pedido_completo(self):
        product = _internal_product()
        resp = self.client.post(reverse("orders:offline_order_create"), {
            "customer_mode": "new",
            "customer_name": "Doña Mary",
            "customer_phone": "4771112233",
            "agreed_price": "1500.00",
            "initial_payment_amount": "500.00",
            "initial_payment_method": "CASH",
            "items-TOTAL": "1",
            "items-0-product_id": str(product.pk),
            "items-0-quantity": "2",
            "items-0-talla": "M",
            "items-0-notas": "logo dorado",
        })
        order = Order.objects.get(order_type="OFFLINE")
        self.assertRedirects(
            resp, reverse("orders:admin_order_detail", args=[order.pk]),
            fetch_redirect_response=False,
        )
        self.assertEqual(order.status, "PENDING")
        self.assertEqual(order.payment_status, "ANTICIPO")

    def test_post_con_producto_nuevo(self):
        resp = self.client.post(reverse("orders:offline_order_create"), {
            "customer_mode": "new",
            "customer_name": "Cliente X",
            "agreed_price": "3500.00",
            "items-TOTAL": "1",
            "items-0-new_product_name": "Traje mascota",
            "items-0-new_product_price": "3500.00",
            "items-0-quantity": "1",
        })
        order = Order.objects.get(order_type="OFFLINE")
        self.assertEqual(order.items.get().product.name, "Traje mascota")

    def test_registrar_abono(self):
        product = _internal_product()
        from orders.services.offline import OfflineOrderService
        order = OfflineOrderService.create(
            admin_user=self.admin, customer_data={"name": "Z"},
            items=[{"product_id": product.pk, "quantity": 1}],
            agreed_price=Decimal("1000.00"),
        )
        resp = self.client.post(
            reverse("orders:register_payment", args=[order.pk]),
            {"amount": "1000.00", "method": "TRANSFER", "notes": ""},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(order.payment_status, "LIQUIDADO")

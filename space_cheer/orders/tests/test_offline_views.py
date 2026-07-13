"""Tests de vistas de pedidos offline (permisos + flujo de captura)."""
from decimal import Decimal

import pytest
from django.test import TestCase
from django.urls import reverse

from orders.models import Order
from orders.tests.factories import (
    CustomerFactory,
    MeasurementFieldFactory,
    ProductFactory,
    ProductMeasurementFieldFactory,
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

    def test_post_sin_agreed_price_no_500(self):
        # POST malformado (sin agreed_price) debe redirigir con error,
        # no propagar un KeyError sin capturar (500).
        product = _internal_product()
        resp = self.client.post(reverse("orders:offline_order_create"), {
            "customer_mode": "new",
            "customer_name": "Cliente Sin Precio",
            "items-TOTAL": "1",
            "items-0-product_id": str(product.pk),
            "items-0-quantity": "1",
            # agreed_price deliberadamente ausente del POST.
        })
        self.assertRedirects(
            resp, reverse("orders:offline_order_create"),
            fetch_redirect_response=False,
        )
        self.assertFalse(Order.objects.filter(order_type="OFFLINE").exists())

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

    def test_registrar_abono_excede_precio_muestra_mensaje_limpio(self):
        """F11 (hallazgo 6.3): el error de sobrepago no debe exponer el
        dict crudo de ValidationError ({'__all__': [...]})."""
        product = _internal_product()
        from orders.services.offline import OfflineOrderService
        order = OfflineOrderService.create(
            admin_user=self.admin, customer_data={"name": "Sobrepago"},
            items=[{"product_id": product.pk, "quantity": 1}],
            agreed_price=Decimal("1000.00"),
        )
        resp = self.client.post(
            reverse("orders:register_payment", args=[order.pk]),
            {"amount": "1200.00", "method": "TRANSFER", "notes": ""},
            follow=True,
        )
        messages_text = " ".join(str(m) for m in resp.context["messages"])
        self.assertIn("exceder", messages_text)
        self.assertNotIn("__all__", messages_text)
        self.assertNotIn("{", messages_text)


class AdminIntegrationTests(TestCase):
    def setUp(self):
        self.admin = _admin()
        self.client.force_login(self.admin)
        from orders.services.offline import OfflineOrderService
        self.order = OfflineOrderService.create(
            admin_user=self.admin, customer_data={"name": "Doña Mary"},
            items=[{"product_id": _internal_product().pk, "quantity": 1}],
            agreed_price=Decimal("1000.00"),
        )

    def test_lista_admin_muestra_badge_offline(self):
        resp = self.client.get(reverse("orders:admin_order_list"))
        self.assertContains(resp, "Personal (offline)")

    def test_filtro_por_tipo(self):
        resp = self.client.get(reverse("orders:admin_order_list") + "?type=OFFLINE")
        self.assertContains(resp, f"#{self.order.pk}")
        resp = self.client.get(reverse("orders:admin_order_list") + "?type=TEAM")
        self.assertNotContains(resp, "Doña Mary")

    def test_detalle_muestra_cliente_y_pagos(self):
        resp = self.client.get(reverse("orders:admin_order_detail", args=[self.order.pk]))
        self.assertContains(resp, "Doña Mary")
        self.assertContains(resp, "1000")


class PaymentFormVisibilityInProductionTests(TestCase):
    """
    Finding (Important) del review final: el form de "Registrar abono" se
    ocultaba con order.can_edit_general, que es False en IN_PRODUCTION —
    justo el estado donde se cobra el saldo final antes de DELIVERED. La
    vista register_payment nunca tuvo guard de status (acepta pagos en
    cualquier estado); el bug era solo de visibilidad en el template.
    """

    def setUp(self):
        self.admin = _admin()
        self.client.force_login(self.admin)
        from orders.services.offline import OfflineOrderService
        from orders.services.state import OrderStateService

        # product_type="OTHER" (no UNIFORM, no requiere diseño): evita los
        # gates de uniform_delivery_date/diseño para poder llegar a
        # IN_PRODUCTION sin ruido ajeno a este test (mismo patrón que
        # OfflineTransitionTests._offline_ready_for_delivery en test_offline.py).
        product = _internal_product(product_type="OTHER")
        self.order = OfflineOrderService.create(
            admin_user=self.admin, customer_data={"name": "Doña Mary"},
            items=[{"product_id": product.pk, "quantity": 1}],
            agreed_price=Decimal("1000.00"),
        )
        # OfflineOrderService.create ya transiciona la orden a PENDING.
        OrderStateService.transition(self.order, "IN_PRODUCTION", self.admin)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "IN_PRODUCTION")

    def test_form_de_abono_visible_en_produccion(self):
        resp = self.client.get(
            reverse("orders:admin_order_detail", args=[self.order.pk])
        )
        self.assertContains(
            resp, reverse("orders:register_payment", args=[self.order.pk])
        )

    def test_registrar_abono_funciona_en_produccion(self):
        resp = self.client.post(
            reverse("orders:register_payment", args=[self.order.pk]),
            {"amount": "1000.00", "method": "CASH", "notes": ""},
        )
        self.assertEqual(resp.status_code, 302)
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, "LIQUIDADO")

    def test_form_de_abono_oculto_una_vez_cerrada_la_orden(self):
        from orders.models import OrderPayment
        from orders.services.state import OrderStateService

        # F3: OFFLINE exige LIQUIDADO siempre para poder entregar.
        OrderPayment.objects.create(
            order=self.order, amount=self.order.agreed_price,
            method="CASH", registered_by=self.admin,
        )
        OrderStateService.transition(self.order, "DELIVERED", self.admin)
        self.order.refresh_from_db()
        self.assertTrue(self.order.closed)

        resp = self.client.get(
            reverse("orders:admin_order_detail", args=[self.order.pk])
        )
        self.assertNotContains(
            resp, reverse("orders:register_payment", args=[self.order.pk])
        )


class ItemMeasurementsPrefillTests(TestCase):
    """Bug: el input medida-<slug> siempre se renderizaba vacío, lo que
    hacía que reenviar el form borrara silenciosamente medidas guardadas
    previamente (save_item_measurements hace reemplazo completo del dict).
    """

    def setUp(self):
        self.admin = _admin()
        self.client.force_login(self.admin)
        self.field = MeasurementFieldFactory(name="Pecho", slug="pecho", unit="cm")
        self.product = _internal_product()
        ProductMeasurementFieldFactory(product=self.product, field=self.field)

        from orders.services.offline import OfflineOrderService

        self.order = OfflineOrderService.create(
            admin_user=self.admin, customer_data={"name": "Doña Mary"},
            items=[{"product_id": self.product.pk, "quantity": 1}],
            agreed_price=Decimal("1000.00"),
        )
        self.item = self.order.items.get()

    def test_medida_guardada_se_prellena_en_el_detalle(self):
        from orders.services.offline import OfflineOrderService

        OfflineOrderService.save_item_measurements(
            item=self.item, medidas={"pecho": "92"},
        )

        resp = self.client.get(reverse("orders:admin_order_detail", args=[self.order.pk]))
        self.assertContains(resp, 'name="medida-pecho" value="92"')

    def test_reenvio_del_form_no_borra_medida_no_incluida(self):
        # Reproduce el escenario del bug: se guarda "pecho" via POST, luego
        # se reenvía el form SIN el campo pecho (como pasaría si el admin no
        # lo ve prellenado y no lo vuelve a escribir). Con el fix, el HTML
        # debe seguir mostrando "92", confirmando que el admin sí puede
        # ver el valor existente antes de decidir sobrescribirlo.
        resp = self.client.post(
            reverse("orders:offline_item_measurements", args=[self.item.pk]),
            {"talla": "M", "notas": "", f"medida-{self.field.slug}": "92"},
        )
        self.assertEqual(resp.status_code, 302)

        resp = self.client.get(reverse("orders:admin_order_detail", args=[self.order.pk]))
        self.assertContains(resp, 'name="medida-pecho" value="92"')

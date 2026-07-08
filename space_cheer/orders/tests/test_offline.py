"""Tests de pedidos personales (offline): Customer, Order OFFLINE, pagos y servicio."""
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from orders.models import Customer, Order, OrderItem, OrderPayment
from orders.services.state import OrderStateService
from orders.tests.factories import (
    CustomerFactory,
    OfflineOrderFactory,
    OrderDesignImageFactory,
    OrderFactory,
    ProductFactory,
    UserFactory,
)


class CustomerModelTests(TestCase):
    def test_customer_externo_sin_user(self):
        c = CustomerFactory(name="Doña Mary", phone="4771234567", user=None)
        self.assertIsNone(c.user)
        self.assertEqual(str(c), "Doña Mary (4771234567)")

    def test_customer_ligado_a_usuario_registrado(self):
        user = UserFactory()
        c = CustomerFactory(user=user)
        self.assertEqual(c.user, user)

    def test_name_es_obligatorio(self):
        c = Customer(name="", created_by=UserFactory())
        with self.assertRaises(ValidationError):
            c.full_clean()


class OrderOfflineTests(TestCase):
    def test_offline_requiere_customer(self):
        with self.assertRaises(ValidationError):
            OfflineOrderFactory(customer=None)

    def test_offline_no_permite_owner_user_ni_team(self):
        from orders.tests.factories import TeamFactory
        with self.assertRaises(ValidationError):
            OfflineOrderFactory(owner_user=UserFactory())
        with self.assertRaises(ValidationError):
            OfflineOrderFactory(owner_team=TeamFactory())

    def test_personal_no_permite_customer(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                # bypass de full_clean para probar el constraint de BD.
                # created_by/owner_user se pasan ya guardados (en vez de
                # dejar que las SubFactory de OrderFactory hereden la
                # estrategia build()) para que bulk_create no falle antes
                # de tiempo por relaciones sin guardar.
                user = UserFactory()
                order = OrderFactory.build(
                    created_by=user, owner_user=user, customer=CustomerFactory()
                )
                Order.objects.bulk_create([order])

    def test_owner_property_devuelve_customer(self):
        order = OfflineOrderFactory()
        self.assertEqual(order.owner, order.customer)

    def test_offline_invisible_para_no_admin(self):
        order = OfflineOrderFactory()
        coach = UserFactory()
        self.assertNotIn(order, Order.objects.visible_for_user(coach))

    def test_offline_visible_para_admin(self):
        from orders.tests.factories import RoleFactory
        admin = UserFactory(roles=[RoleFactory(name="ADMIN")])
        order = OfflineOrderFactory()
        self.assertIn(order, Order.objects.visible_for_user(admin))

    def test_offline_invisible_para_created_by_no_admin(self):
        coach = UserFactory()
        order = OfflineOrderFactory(created_by=coach)
        self.assertNotIn(order, Order.objects.visible_for_user(coach))

    def test_offline_no_permite_cambiar_customer(self):
        order = OfflineOrderFactory()
        order.customer = CustomerFactory()
        with self.assertRaises(ValidationError):
            order.save()


def _internal_product(**kw):
    kw.setdefault("scope", "INTERNAL")
    kw.setdefault("usage_type", "GLOBAL")
    kw.setdefault("size_strategy", "NONE")
    return ProductFactory(**kw)


class OrderItemOfflineTests(TestCase):
    def test_item_offline_guarda_custom_measurements(self):
        order = OfflineOrderFactory()
        item = OrderItem(
            order=order,
            product=_internal_product(),
            quantity=1,
            custom_measurements={"talla": "M", "notas": "logo dorado", "medidas": {}},
        )
        item.save()
        item.refresh_from_db()
        self.assertEqual(item.custom_measurements["talla"], "M")

    def test_producto_internal_rechazado_en_orden_personal(self):
        order = OrderFactory()  # PERSONAL
        item = OrderItem(order=order, product=_internal_product(), quantity=1)
        with self.assertRaises(ValidationError):
            item.save()

    def test_producto_catalog_rechazado_en_orden_offline(self):
        order = OfflineOrderFactory()
        item = OrderItem(order=order, product=ProductFactory(), quantity=1)
        with self.assertRaises(ValidationError):
            item.save()


class OrderPaymentTests(TestCase):
    def setUp(self):
        self.admin = UserFactory()
        self.order = OfflineOrderFactory(agreed_price=Decimal("1000.00"))

    def _pay(self, amount):
        return OrderPayment.objects.create(
            order=self.order, amount=Decimal(amount),
            method="CASH", registered_by=self.admin,
        )

    def test_balance_y_estado(self):
        self.assertEqual(self.order.payment_status, "SIN_PAGOS")
        self._pay("400.00")
        self.assertEqual(self.order.total_paid, Decimal("400.00"))
        self.assertEqual(self.order.balance_due, Decimal("600.00"))
        self.assertEqual(self.order.payment_status, "ANTICIPO")
        self._pay("600.00")
        self.assertEqual(self.order.payment_status, "LIQUIDADO")

    def test_pago_no_puede_exceder_agreed_price(self):
        self._pay("900.00")
        with self.assertRaises(ValidationError):
            self._pay("200.00")

    def test_monto_debe_ser_positivo(self):
        with self.assertRaises(ValidationError):
            self._pay("0.00")

    def test_pago_sin_agreed_price_rechazado(self):
        order = OfflineOrderFactory(agreed_price=None)
        with self.assertRaises(ValidationError):
            OrderPayment.objects.create(
                order=order, amount=Decimal("100.00"),
                method="CASH", registered_by=self.admin,
            )

    def test_pagos_inmutables(self):
        pago = self._pay("100.00")
        pago.amount = Decimal("999.00")
        with self.assertRaises(ValidationError):
            pago.save()
        with self.assertRaises(ValidationError):
            pago.delete()

    def test_pagos_inmutables_via_queryset_delete(self):
        self._pay("100.00")
        with self.assertRaises(ValidationError):
            OrderPayment.objects.filter(order=self.order).delete()


class OfflineTransitionTests(TestCase):
    def setUp(self):
        from orders.tests.factories import RoleFactory
        self.admin = UserFactory(roles=[RoleFactory(name="ADMIN")])

    def _offline_with_item(self, **order_kw):
        order = OfflineOrderFactory(**order_kw)
        OrderItem.objects.create(order=order, product=_internal_product(), quantity=1)
        return order

    def test_pending_valida_agreed_price(self):
        order = self._offline_with_item(agreed_price=None)
        with self.assertRaises(ValidationError):
            OrderStateService.transition(order, "PENDING", self.admin)

    def test_pending_valida_items(self):
        order = OfflineOrderFactory()
        with self.assertRaises(ValidationError):
            OrderStateService.transition(order, "PENDING", self.admin)

    def test_in_production_valida_fecha_entrega_uniforme(self):
        order = self._offline_with_item(uniform_delivery_date=None)
        OrderStateService.transition(order, "PENDING", self.admin)
        with self.assertRaises(ValidationError):
            OrderStateService.transition(order, "IN_PRODUCTION", self.admin)

    def test_flujo_completo_hasta_produccion_crea_job(self):
        from production.models import ProductionStage, ProductStageConfig

        product = _internal_product()
        stage = ProductionStage.objects.create(name="Corte", slug="corte-off", display_order=1)
        ProductStageConfig.objects.create(product=product, stage=stage, display_order=1)

        order = OfflineOrderFactory()
        OrderItem.objects.create(order=order, product=product, quantity=1)

        OrderStateService.transition(order, "PENDING", self.admin)
        OrderStateService.transition(order, "IN_PRODUCTION", self.admin)
        order.refresh_from_db()
        self.assertEqual(order.status, "IN_PRODUCTION")
        self.assertTrue(hasattr(order, "production_job"))
        self.assertEqual(order.production_job.tasks.count(), 1)

    @patch("orders.services.notifications.order_notifications.OrderNotificationService._send_email")
    def test_notificacion_omitida_para_cliente_externo(self, mock_send):
        order = self._offline_with_item()  # customer sin user
        OrderStateService.transition(order, "PENDING", self.admin)
        OrderStateService.transition(order, "IN_PRODUCTION", self.admin)
        mock_send.assert_not_called()

    @patch("orders.services.notifications.order_notifications.OrderNotificationService._send_email")
    def test_notificacion_enviada_si_customer_tiene_user(self, mock_send):
        user = UserFactory(email="cliente@test.com")
        order = self._offline_with_item(customer=CustomerFactory(user=user))
        OrderStateService.transition(order, "PENDING", self.admin)
        OrderStateService.transition(order, "IN_PRODUCTION", self.admin)
        mock_send.assert_called()
        args_to = mock_send.call_args[0][1]
        self.assertIn("cliente@test.com", args_to)

    def _offline_ready_for_delivery(self, *, requires_design, agreed_price=Decimal("1000.00")):
        """Orden OFFLINE transicionada hasta IN_PRODUCTION, lista para intentar DELIVERED."""
        order = OfflineOrderFactory(agreed_price=agreed_price)
        # product_type="OTHER" evita el gate de uniform_delivery_date, que no
        # es lo que este set de tests quiere ejercitar.
        if requires_design:
            product = _internal_product(
                usage_type="TEAM_CUSTOM", size_strategy="MEASUREMENTS", product_type="OTHER"
            )
        else:
            product = _internal_product(product_type="OTHER")
        OrderItem.objects.create(order=order, product=product, quantity=1)
        if requires_design:
            OrderDesignImageFactory(order=order, is_final=True)
        OrderStateService.transition(order, "PENDING", self.admin)
        OrderStateService.transition(order, "IN_PRODUCTION", self.admin)
        return order

    def test_delivered_offline_con_diseno_exige_payment_status_liquidado(self):
        order = self._offline_ready_for_delivery(requires_design=True)
        # anticipo parcial: no liquida el saldo
        OrderPayment.objects.create(
            order=order, amount=Decimal("400.00"), method="CASH", registered_by=self.admin,
        )
        self.assertEqual(order.payment_status, "ANTICIPO")
        with self.assertRaises(ValidationError):
            OrderStateService.transition(order, "DELIVERED", self.admin)

    def test_delivered_offline_con_diseno_pasa_si_liquidado(self):
        order = self._offline_ready_for_delivery(requires_design=True)
        OrderPayment.objects.create(
            order=order, amount=order.agreed_price, method="CASH", registered_by=self.admin,
        )
        self.assertEqual(order.payment_status, "LIQUIDADO")
        OrderStateService.transition(order, "DELIVERED", self.admin)
        order.refresh_from_db()
        self.assertEqual(order.status, "DELIVERED")

    def test_delivered_offline_sin_diseno_no_exige_liquidacion(self):
        order = self._offline_ready_for_delivery(requires_design=False)
        self.assertEqual(order.payment_status, "SIN_PAGOS")
        OrderStateService.transition(order, "DELIVERED", self.admin)
        order.refresh_from_db()
        self.assertEqual(order.status, "DELIVERED")

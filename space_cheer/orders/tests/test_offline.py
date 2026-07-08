"""Tests de pedidos personales (offline): Customer, Order OFFLINE, pagos y servicio."""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from orders.models import Customer, Order, OrderItem, OrderPayment
from orders.tests.factories import (
    CustomerFactory,
    OfflineOrderFactory,
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

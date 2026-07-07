"""Tests de pedidos personales (offline): Customer, Order OFFLINE, pagos y servicio."""
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from orders.models import Customer, Order
from orders.tests.factories import (
    CustomerFactory,
    OfflineOrderFactory,
    OrderFactory,
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

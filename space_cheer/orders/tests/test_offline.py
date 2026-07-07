"""Tests de pedidos personales (offline): Customer, Order OFFLINE, pagos y servicio."""
from django.core.exceptions import ValidationError
from django.test import TestCase

from orders.models import Customer
from orders.tests.factories import CustomerFactory, UserFactory


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

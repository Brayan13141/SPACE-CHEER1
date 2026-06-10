from django.test import TestCase
from django.contrib.auth import get_user_model

from accounts.models import Role

User = get_user_model()


class RoleModelTests(TestCase):

    def test_role_has_is_production_type_with_default_false(self):
        """Role debe tener campo is_production_type con default False"""
        role = Role.objects.create(name="TEST_ROLE")
        self.assertFalse(role.is_production_type)

    def test_operario_role_has_is_production_type_true(self):
        """El rol OPERARIO debe crearse con is_production_type=True"""
        role = Role.objects.create(name="OPERARIO", is_production_type=True)
        self.assertTrue(role.is_production_type)

    def test_operario_role_signal_is_not_unknown_role(self):
        """Asignar OPERARIO no debe registrarse como rol desconocido."""
        role = Role.objects.create(name="OPERARIO", is_production_type=True)
        user = User.objects.create_user(
            username="op_test",
            email="op_test@example.com",
            password="TestPass123!",
        )

        with self.assertLogs("space_cheer", level="INFO") as logs:
            user.roles.add(role)

        self.assertTrue(
            any("Rol de produccion" in message for message in logs.output)
        )
        self.assertFalse(
            any("Rol desconocido" in message for message in logs.output)
        )

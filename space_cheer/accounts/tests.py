from django.test import TestCase
from accounts.models import Role


class RoleModelTests(TestCase):

    def test_role_has_is_production_type_with_default_false(self):
        """Role debe tener campo is_production_type con default False"""
        role = Role.objects.create(name="TEST_ROLE")
        self.assertFalse(role.is_production_type)

    def test_operario_role_has_is_production_type_true(self):
        """El rol OPERARIO debe crearse con is_production_type=True"""
        role = Role.objects.create(name="OPERARIO", is_production_type=True)
        self.assertTrue(role.is_production_type)

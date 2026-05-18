from django.test import TestCase, Client
from django.urls import reverse

from accounts.models import Role
from orders.tests.factories import UserFactory


def make_user_with_role(role_name, **role_kwargs):
    user = UserFactory(profile_completed=True)
    role, _ = Role.objects.get_or_create(name=role_name, defaults=role_kwargs)
    user.roles.add(role)
    return user


class UserRolesContextProcessorTests(TestCase):

    def _get_context(self, user):
        client = Client()
        client.force_login(user)
        response = client.get(reverse("core:dashboard"))
        return response.context

    def test_is_operario_true_for_operario_role(self):
        user = make_user_with_role("OPERARIO", is_production_type=True)
        ctx = self._get_context(user)
        self.assertTrue(ctx["is_operario"])

    def test_is_operario_false_for_non_operario(self):
        user = make_user_with_role("COACH")
        ctx = self._get_context(user)
        self.assertFalse(ctx["is_operario"])


class DashboardProductionLinksTests(TestCase):

    def _get(self, user):
        client = Client()
        client.force_login(user)
        return client.get(reverse("core:dashboard"))

    def test_operario_sees_production_dashboard_link(self):
        user = make_user_with_role("OPERARIO", is_production_type=True)
        response = self._get(user)
        self.assertContains(response, reverse("production:dashboard"))

    def test_admin_sees_production_overview_link(self):
        user = make_user_with_role("ADMIN")
        response = self._get(user)
        self.assertContains(response, reverse("production:admin_overview"))

    def test_staff_sees_production_overview_link(self):
        user = make_user_with_role("STAFF", is_staff_type=True)
        response = self._get(user)
        self.assertContains(response, reverse("production:admin_overview"))

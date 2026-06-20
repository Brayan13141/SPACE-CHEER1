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


from unittest.mock import MagicMock
from core.help_registry import get_help_text


class GetHelpTextTests(TestCase):

    def _user(self, *role_names):
        user = MagicMock()
        user.is_authenticated = True
        user.roles.values_list.return_value = list(role_names)
        return user

    def test_role_specific_text_returned(self):
        user = self._user("ADMIN")
        self.assertIn("administración", get_help_text("core:dashboard", user))

    def test_first_matching_role_wins(self):
        # user has both ATHLETE and ADMIN; ADMIN entry exists, ATHLETE does not for dashboard
        user = self._user("ADMIN", "ATHLETE")
        self.assertNotEqual(get_help_text("core:dashboard", user), "")

    def test_none_fallback_when_no_role_match(self):
        user = self._user("ATHLETE")
        # orders:manage_orders has a None-keyed entry
        self.assertNotEqual(get_help_text("orders:manage_orders", user), "")

    def test_unauthenticated_returns_empty(self):
        user = MagicMock()
        user.is_authenticated = False
        self.assertEqual(get_help_text("core:dashboard", user), "")

    def test_unknown_view_returns_empty(self):
        user = self._user("ADMIN")
        self.assertEqual(get_help_text("nonexistent:view", user), "")

    def test_none_user_returns_empty(self):
        self.assertEqual(get_help_text("core:dashboard", None), "")

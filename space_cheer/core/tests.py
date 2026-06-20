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


class PageHelpContextProcessorTests(TestCase):

    def _get(self, user, url_name, **kwargs):
        client = Client()
        client.force_login(user)
        return client.get(reverse(url_name, **kwargs))

    def test_page_help_text_present_for_admin_dashboard(self):
        user = make_user_with_role("ADMIN")
        response = self._get(user, "core:dashboard")
        self.assertIn("page_help_text", response.context)
        self.assertIn("administración", response.context["page_help_text"])

    def test_page_help_text_empty_for_unregistered_view(self):
        # accounts:profile_settings has no registry entry
        user = make_user_with_role("ADMIN")
        response = self._get(user, "accounts:profile_settings")
        self.assertEqual(response.context["page_help_text"], "")


from django.template import Context, Template


class HelpIconTagTests(TestCase):

    def _render(self, snippet):
        tpl = Template("{% load help_tags %}" + snippet)
        return tpl.render(Context({}))

    def test_renders_popover_button(self):
        html = self._render('{% help_icon "Texto de ayuda." %}')
        self.assertIn('data-bs-toggle="popover"', html)
        self.assertIn("Texto de ayuda.", html)
        self.assertIn("bi-info-circle", html)

    def test_default_placement_is_top(self):
        html = self._render('{% help_icon "Test." %}')
        self.assertIn('data-bs-placement="top"', html)

    def test_custom_placement(self):
        html = self._render('{% help_icon "Test." "right" %}')
        self.assertIn('data-bs-placement="right"', html)

    def test_trigger_is_hover_focus(self):
        html = self._render('{% help_icon "Test." %}')
        self.assertIn('data-bs-trigger="hover focus"', html)

    def test_has_aria_label(self):
        html = self._render('{% help_icon "Test." %}')
        self.assertIn('aria-label="Más información"', html)


class RegistrySpotCheckTests(TestCase):

    def _user(self, *role_names):
        user = MagicMock()
        user.is_authenticated = True
        user.roles.values_list.return_value = list(role_names)
        return user

    def test_operario_gets_operario_text_on_production_dashboard(self):
        text = get_help_text("production:dashboard", self._user("OPERARIO"))
        self.assertIn("tareas", text)

    def test_headcoach_gets_headcoach_text_on_dashboard(self):
        text = get_help_text("core:dashboard", self._user("HEADCOACH"))
        self.assertIn("equipo", text)

    def test_guardian_gets_guardian_text_on_dashboard(self):
        text = get_help_text("core:dashboard", self._user("GUARDIAN"))
        self.assertIn("tutor", text)

    def test_none_keyed_entry_serves_all_roles(self):
        for role in ("ADMIN", "HEADCOACH", "ATHLETE", "COACH"):
            with self.subTest(role=role):
                text = get_help_text("orders:manage_orders", self._user(role))
                self.assertNotEqual(text, "")

    def test_athlete_gets_catalog_text(self):
        text = get_help_text("products:catalog", self._user("ATHLETE"))
        self.assertIn("Catálogo", text)

    def test_admin_gets_operarios_management_text(self):
        text = get_help_text("production:manage_operarios", self._user("ADMIN"))
        self.assertIn("operarios", text.lower())

    def test_error_report_list_differs_by_role(self):
        admin_text = get_help_text("production:error_report_list", self._user("ADMIN"))
        op_text = get_help_text("production:error_report_list", self._user("OPERARIO"))
        self.assertNotEqual(admin_text, op_text)

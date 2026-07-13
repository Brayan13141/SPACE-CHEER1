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
from core.help_registry import get_help_text, get_help_cards


class GetHelpTextTests(TestCase):

    def _user(self, *role_names):
        user = MagicMock()
        user.is_authenticated = True
        user.help_dismissed = False
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
        from django.core.cache import cache
        cache.clear()  # core:privacy usa @cache_page; el hit cacheado no trae context
        client = Client()
        client.force_login(user)
        return client.get(reverse(url_name, **kwargs))

    def test_page_help_text_present_for_admin_dashboard(self):
        user = make_user_with_role("ADMIN")
        response = self._get(user, "core:dashboard")
        self.assertIn("page_help_text", response.context)
        self.assertIn("administración", response.context["page_help_text"])

    def test_page_help_text_empty_for_unregistered_view(self):
        # core:privacy intencionalmente sin entrada en el registry (página legal)
        user = make_user_with_role("ADMIN")
        response = self._get(user, "core:privacy")
        self.assertEqual(response.context["page_help_text"], "")

    def test_page_help_cards_present_for_admin_dashboard(self):
        user = make_user_with_role("ADMIN")
        response = self._get(user, "core:dashboard")
        self.assertIn("page_help_cards", response.context)
        self.assertGreaterEqual(len(response.context["page_help_cards"]), 2)

    def test_page_help_cards_empty_for_unregistered_view(self):
        user = make_user_with_role("ADMIN")
        response = self._get(user, "core:privacy")
        self.assertEqual(response.context["page_help_cards"], [])

    def test_page_help_text_is_first_card(self):
        user = make_user_with_role("ADMIN")
        response = self._get(user, "core:dashboard")
        self.assertEqual(
            response.context["page_help_text"],
            response.context["page_help_cards"][0],
        )


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
        user.help_dismissed = False
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


class GetHelpCardsTests(TestCase):
    """v2: get_help_cards returns list[str]."""

    def _user(self, *role_names, dismissed=False):
        user = MagicMock()
        user.is_authenticated = True
        user.help_dismissed = dismissed
        user.roles.values_list.return_value = list(role_names)
        return user

    def test_returns_list_of_cards_for_role_entry(self):
        cards = get_help_cards("core:dashboard", self._user("ADMIN"))
        self.assertIsInstance(cards, list)
        self.assertGreaterEqual(len(cards), 2)
        self.assertTrue(all(isinstance(c, str) for c in cards))

    def test_unauthenticated_returns_empty_list(self):
        user = MagicMock()
        user.is_authenticated = False
        self.assertEqual(get_help_cards("core:dashboard", user), [])

    def test_none_user_returns_empty_list(self):
        self.assertEqual(get_help_cards("core:dashboard", None), [])

    def test_dismissed_user_returns_empty_list(self):
        cards = get_help_cards("core:dashboard", self._user("ADMIN", dismissed=True))
        self.assertEqual(cards, [])

    def test_unknown_view_returns_empty_list(self):
        self.assertEqual(get_help_cards("nope:view", self._user("ADMIN")), [])

    def test_none_fallback_serves_all_roles(self):
        cards = get_help_cards("orders:manage_orders", self._user("ATHLETE"))
        self.assertGreaterEqual(len(cards), 2)

    def test_first_matching_role_wins(self):
        cards = get_help_cards("core:dashboard", self._user("ADMIN", "ATHLETE"))
        self.assertGreaterEqual(len(cards), 1)

    def test_events_list_has_three_cards(self):
        cards = get_help_cards("events:event_list", self._user("ATHLETE"))
        self.assertEqual(len(cards), 3)

    def test_social_send_invite_present(self):
        cards = get_help_cards("social:send_invite", self._user("HEADCOACH"))
        self.assertGreaterEqual(len(cards), 2)

    def test_hospitality_index_present(self):
        cards = get_help_cards("hospitality:index", self._user("ATHLETE"))
        self.assertGreaterEqual(len(cards), 2)

    def test_get_help_text_returns_first_card(self):
        """Backward compat: get_help_text returns first card of the list."""
        cards = get_help_cards("core:dashboard", self._user("ADMIN"))
        text = get_help_text("core:dashboard", self._user("ADMIN"))
        self.assertEqual(text, cards[0])


class RegistryFullCoverageTests(TestCase):
    """Toda página navegable (GET con template) debe tener ayuda registrada.

    Se excluyen: red social (decisión de producto), páginas legales
    (privacy/terminos), páginas de allauth (usuario anónimo → sin FAB) y
    endpoints solo-POST/JSON que no renderizan página propia.
    """

    def _user(self, *role_names):
        user = MagicMock()
        user.is_authenticated = True
        user.help_dismissed = False
        user.roles.values_list.return_value = list(role_names)
        return user

    # (view_name, rol con el que debe resolver ayuda)
    EXPECTED_COVERAGE = [
        # core
        ("core:landing", "ATHLETE"),
        ("core:manage_landing", "ADMIN"),
        ("core:contact", "ATHLETE"),
        # accounts
        ("accounts:profile_settings", "ATHLETE"),
        ("accounts:list_address", "ATHLETE"),
        ("accounts:create_address", "ATHLETE"),
        ("accounts:update_address", "ATHLETE"),
        ("accounts:curp_verification", "ATHLETE"),
        ("accounts:bulk_import_athletes", "HEADCOACH"),
        ("accounts:coach_pending_approval", "HEADCOACH"),
        ("accounts:coach_rejected", "HEADCOACH"),
        ("accounts:account_deactivate", "ATHLETE"),
        # guardian / custodia
        ("guardian:assign_guardian", "HEADCOACH"),
        ("guardian:minor_blocked", "ATHLETE"),
        ("guardian:create_order_for_minor", "GUARDIAN"),
        # coach
        ("coach:edit_athlete_measures", "COACH"),
        ("coach:edit_owned_user", "COACH"),
        ("coach:create_team_crew_member", "HEADCOACH"),
        # teams
        ("teams:coach_teams", "COACH"),
        ("teams:join_by_code", "ATHLETE"),
        ("teams:manage_categories", "ADMIN"),
        ("teams:manage_team_members", "HEADCOACH"),
        # orders (usuario)
        ("orders:edit_order", "HEADCOACH"),
        ("orders:contact_info_order", "HEADCOACH"),
        ("orders:order_item_detail", "HEADCOACH"),
        ("orders:cart_team_select", "HEADCOACH"),
        # orders (admin / offline)
        ("orders:customer_list", "ADMIN"),
        ("orders:offline_order_create", "ADMIN"),
        # production
        ("production:mi_area", "OPERARIO"),
        ("production:reglamento", "OPERARIO"),
        ("production:admin_job_detail", "ADMIN"),
        ("production:error_report_detail", "OPERARIO"),
        ("production:item_measurements", "OPERARIO"),
        ("production:order_design", "OPERARIO"),
        ("production:manage_responsibilities", "ADMIN"),
        ("production:manage_templates", "ADMIN"),
        ("production:product_stages_matrix", "ADMIN"),
        ("production:operario_detail", "ADMIN"),
        ("production:manage_role_operarios", "ADMIN"),
        # products
        ("products:create_product", "ADMIN"),
        ("products:select_template", "ADMIN"),
        # events
        ("events:event_edit", "ADMIN"),
        ("events:my_registrations", "HEADCOACH"),
        ("events:team_register", "HEADCOACH"),
        ("events:registrations_list", "ADMIN"),
        ("events:staff_manage", "ADMIN"),
        ("events:criteria_manage", "ADMIN"),
        ("events:score_entry", "ADMIN"),
        ("events:results_manage", "ADMIN"),
        ("events:judge_panel", "ATHLETE"),
        # hospitality
        ("hospitality:hotel_detail", "ADMIN"),
        ("hospitality:hotel_create", "ADMIN"),
        ("hospitality:hotel_edit", "ADMIN"),
        ("hospitality:room_type_create", "ADMIN"),
        ("hospitality:room_type_edit", "ADMIN"),
        ("hospitality:room_create", "ADMIN"),
        ("hospitality:room_edit", "ADMIN"),
        ("hospitality:bed_create", "ADMIN"),
        ("hospitality:stay_list", "ADMIN"),
        ("hospitality:stay_create", "ADMIN"),
        ("hospitality:stay_detail", "ADMIN"),
        ("hospitality:stay_confirm", "ADMIN"),
        ("hospitality:room_assign", "ADMIN"),
        ("hospitality:bed_assign", "ADMIN"),
        ("hospitality:preference_form", "ATHLETE"),
        ("hospitality:room_feature_list", "ADMIN"),
        ("hospitality:room_feature_create", "ADMIN"),
        ("hospitality:room_feature_edit", "ADMIN"),
    ]

    def test_every_expected_view_has_help_cards(self):
        for view_name, role in self.EXPECTED_COVERAGE:
            with self.subTest(view=view_name, role=role):
                cards = get_help_cards(view_name, self._user(role))
                self.assertGreaterEqual(
                    len(cards), 2,
                    f"{view_name} (rol {role}) sin ayuda registrada",
                )

    def test_legal_pages_have_no_help(self):
        for view_name in ("core:privacy", "core:terminos"):
            with self.subTest(view=view_name):
                self.assertEqual(get_help_cards(view_name, self._user("ADMIN")), [])


class HelpFabRenderTests(TestCase):

    def _get(self, user, url_name):
        from django.core.cache import cache
        cache.clear()  # core:privacy usa @cache_page
        client = Client()
        client.force_login(user)
        return client.get(reverse(url_name))

    def test_modal_rendered_when_cards_present(self):
        user = make_user_with_role("ADMIN")
        response = self._get(user, "core:dashboard")
        self.assertContains(response, 'id="scHelpModal"')
        self.assertContains(response, 'id="scHelpCarousel"')
        self.assertContains(response, "carousel-item")

    def test_fab_hidden_when_no_cards(self):
        # core:privacy intencionalmente sin entrada en el registry → no FAB/modal
        user = make_user_with_role("ADMIN")
        response = self._get(user, "core:privacy")
        self.assertNotContains(response, 'id="scHelpModal"')

    def test_modal_hidden_when_help_dismissed(self):
        user = make_user_with_role("ADMIN")
        user.help_dismissed = True
        user.save(update_fields=["help_dismissed"])
        response = self._get(user, "core:dashboard")
        self.assertNotContains(response, 'id="scHelpModal"')

    def test_settings_shows_reactivate_when_dismissed(self):
        user = make_user_with_role("ADMIN")
        user.help_dismissed = True
        user.save(update_fields=["help_dismissed"])
        response = self._get(user, "accounts:profile_settings")
        self.assertContains(response, 'value="enable"')


class HelpAutoOpenTests(TestCase):
    """Primera visita a una página con ayuda → el modal se abre solo (una vez).

    El JS usa localStorage con llave por view_name; aquí verificamos que el
    template exponga lo necesario: data-help-view en el modal y el script.
    """

    def _get(self, user, url_name):
        from django.core.cache import cache
        cache.clear()
        client = Client()
        client.force_login(user)
        return client.get(reverse(url_name))

    def test_context_has_page_help_view(self):
        user = make_user_with_role("ADMIN")
        response = self._get(user, "core:dashboard")
        self.assertEqual(response.context["page_help_view"], "core:dashboard")

    def test_modal_carries_view_name_attribute(self):
        user = make_user_with_role("ADMIN")
        response = self._get(user, "core:dashboard")
        self.assertContains(response, 'data-help-view="core:dashboard"')

    def test_auto_open_script_present_with_cards(self):
        user = make_user_with_role("ADMIN")
        response = self._get(user, "core:dashboard")
        self.assertContains(response, "sc_help_seen:")

    def test_auto_open_absent_when_dismissed(self):
        user = make_user_with_role("ADMIN")
        user.help_dismissed = True
        user.save(update_fields=["help_dismissed"])
        response = self._get(user, "core:dashboard")
        self.assertNotContains(response, "sc_help_seen:")


class HelpDismissedFieldTests(TestCase):

    def test_defaults_false(self):
        user = make_user_with_role("ATHLETE", is_athlete_type=True)
        self.assertFalse(user.help_dismissed)


class ToggleHelpViewTests(TestCase):

    def _client(self, user):
        client = Client()
        client.force_login(user)
        return client

    def test_anonymous_redirected(self):
        response = Client().post(reverse("accounts:toggle_help"))
        self.assertEqual(response.status_code, 302)

    def test_get_not_allowed(self):
        user = make_user_with_role("ATHLETE", is_athlete_type=True)
        response = self._client(user).get(reverse("accounts:toggle_help"))
        self.assertEqual(response.status_code, 405)

    def test_dismiss_sets_flag_true(self):
        user = make_user_with_role("ATHLETE", is_athlete_type=True)
        response = self._client(user).post(
            reverse("accounts:toggle_help"),
            {"action": "dismiss", "next": "/"},
        )
        self.assertEqual(response.status_code, 302)
        user.refresh_from_db()
        self.assertTrue(user.help_dismissed)

    def test_enable_sets_flag_false(self):
        user = make_user_with_role("ATHLETE", is_athlete_type=True)
        user.help_dismissed = True
        user.save(update_fields=["help_dismissed"])
        response = self._client(user).post(
            reverse("accounts:toggle_help"),
            {"action": "enable", "next": "/"},
        )
        self.assertEqual(response.status_code, 302)
        user.refresh_from_db()
        self.assertFalse(user.help_dismissed)

    def test_default_action_is_dismiss(self):
        user = make_user_with_role("ATHLETE", is_athlete_type=True)
        self._client(user).post(reverse("accounts:toggle_help"), {"next": "/"})
        user.refresh_from_db()
        self.assertTrue(user.help_dismissed)

    def test_external_next_is_rejected(self):
        """Open redirect guard: external next falls back to '/'."""
        user = make_user_with_role("ATHLETE", is_athlete_type=True)
        response = self._client(user).post(
            reverse("accounts:toggle_help"),
            {"action": "dismiss", "next": "https://evil.example.com/phish"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/")

    def test_safe_relative_next_is_honored(self):
        user = make_user_with_role("ATHLETE", is_athlete_type=True)
        response = self._client(user).post(
            reverse("accounts:toggle_help"),
            {"action": "dismiss", "next": "/accounts/profile/settings/"},
        )
        self.assertEqual(response["Location"], "/accounts/profile/settings/")

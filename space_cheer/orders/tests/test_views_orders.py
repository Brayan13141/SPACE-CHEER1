# orders/tests/test_views_orders.py

from urllib import response

import pytest
from django.test import TestCase, Client
from django.urls import reverse


from orders.models import Order, OrderContactInfo
from orders.tests.factories import (
    UserFactory,
    CoachFactory,
    TeamFactory,
    OrderFactory,
    OrderContactInfoFactory,
    OrderItemFactory,
    ProductFactory,
)


# ===========================================================
# ORDER LIST
# ===========================================================


@pytest.mark.django_db
class OrderListViewTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.coach = CoachFactory()
        self.client.force_login(self.coach)

    def test_order_list_requires_login(self):
        self.client.logout()
        url = reverse("orders:manage_orders")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/", response["Location"])

    def test_order_list_returns_200_for_authenticated(self):
        url = reverse("orders:manage_orders")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_order_list_shows_only_user_orders(self):
        """Un usuario NO ve órdenes de otro usuario."""
        my_order = OrderFactory(created_by=self.coach, owner_user=self.coach)

        other_user = CoachFactory()
        other_order = OrderFactory(created_by=other_user, owner_user=other_user)

        url = reverse("orders:manage_orders")
        response = self.client.get(url)

        order_ids = [o.id for o in response.context["orders"]]
        self.assertIn(my_order.id, order_ids)
        self.assertNotIn(other_order.id, order_ids)

    def test_order_list_filter_active_excludes_delivered(self):
        active_order = OrderFactory(created_by=self.coach, owner_user=self.coach)

        delivered_order = OrderFactory(created_by=self.coach, owner_user=self.coach)
        delivered_order._allow_status_change = True
        delivered_order.status = "DELIVERED"
        delivered_order.closed = True
        delivered_order.save(update_fields=["status", "closed"])

        url = reverse("orders:manage_orders") + "?filter=active"
        response = self.client.get(url)
        order_ids = [o.id for o in response.context["orders"]]

        self.assertIn(active_order.id, order_ids)
        self.assertNotIn(delivered_order.id, order_ids)

    def test_order_list_filter_finalized_shows_delivered(self):
        active_order = OrderFactory(created_by=self.coach, owner_user=self.coach)

        delivered_order = OrderFactory(created_by=self.coach, owner_user=self.coach)
        delivered_order._allow_status_change = True
        delivered_order.status = "DELIVERED"
        delivered_order.closed = True
        delivered_order.save(update_fields=["status", "closed"])

        url = reverse("orders:manage_orders") + "?filter=finalized"
        response = self.client.get(url)
        order_ids = [o.id for o in response.context["orders"]]

        self.assertNotIn(active_order.id, order_ids)
        self.assertIn(delivered_order.id, order_ids)

    def test_coach_sees_team_orders_as_coach(self):
        """El coach ve órdenes de sus equipos."""
        team = TeamFactory(coach=self.coach)
        team_order = OrderFactory(
            order_type="TEAM",
            owner_team=team,
            owner_user=None,
            created_by=self.coach,
        )

        url = reverse("orders:manage_orders")
        response = self.client.get(url)
        order_ids = [o.id for o in response.context["orders"]]
        self.assertIn(team_order.id, order_ids)

    def test_context_has_filter_status(self):
        url = reverse("orders:manage_orders") + "?filter=finalized"
        response = self.client.get(url)
        self.assertEqual(response.context["filter_status"], "finalized")

    def test_superuser_sees_all_orders(self):
        superuser = UserFactory(is_superuser=True)
        self.client.force_login(superuser)

        other_coach = CoachFactory()
        other_order = OrderFactory(created_by=other_coach, owner_user=other_coach)

        url = reverse("orders:manage_orders")
        response = self.client.get(url)
        order_ids = [o.id for o in response.context["orders"]]
        self.assertIn(other_order.id, order_ids)


# ===========================================================
# ORDER CREATE
# ===========================================================


@pytest.mark.django_db
class OrderCreateViewTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.coach = CoachFactory()
        self.client.force_login(self.coach)

    def test_get_returns_200(self):
        url = reverse("orders:create_order")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_get_requires_login(self):
        self.client.logout()
        url = reverse("orders:create_order")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

    def test_create_team_order_requires_team_selection(self):
        team = TeamFactory(coach=self.coach)
        url = reverse("orders:create_order")

        # Sin equipo → error
        response = self.client.post(
            url,
            {
                "order_type": "TEAM",
                # order_team ausente
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("error", response.context)

    def test_cannot_create_team_order_with_foreign_team(self):
        """No puedes crear orden con equipo de otro coach."""
        other_coach = CoachFactory()
        other_team = TeamFactory(coach=other_coach)

        url = reverse("orders:create_order")
        response = self.client.post(
            url,
            {
                "order_type": "TEAM",
                "order_team": other_team.id,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("error", response.context)

    def test_invalid_order_type_shows_error(self):
        url = reverse("orders:create_order")
        response = self.client.post(url, {"order_type": "INVALIDO"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("error", response.context)

    def test_context_has_teams(self):
        team = TeamFactory(coach=self.coach)
        url = reverse("orders:create_order")
        response = self.client.get(url)
        self.assertIn("teams", response.context)
        self.assertIn(team, response.context["teams"])


# ===========================================================
# ORDER DETAIL
# ===========================================================


@pytest.mark.django_db
class OrderDetailViewTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.coach = CoachFactory()
        self.order = OrderFactory(created_by=self.coach, owner_user=self.coach)
        self.client.force_login(self.coach)

    def test_owner_can_view_order(self):
        url = reverse("orders:detail_order", kwargs={"order_id": self.order.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_other_user_gets_404(self):
        other_user = CoachFactory()
        self.client.force_login(other_user)
        url = reverse("orders:detail_order", kwargs={"order_id": self.order.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_unauthenticated_redirects(self):
        self.client.logout()
        url = reverse("orders:detail_order", kwargs={"order_id": self.order.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

    def test_context_has_blocking_issues(self):
        url = reverse("orders:detail_order", kwargs={"order_id": self.order.id})
        response = self.client.get(url)
        self.assertIn("blocking_issues", response.context)

    def test_context_has_available_transitions(self):
        url = reverse("orders:detail_order", kwargs={"order_id": self.order.id})
        response = self.client.get(url)
        self.assertIn("available_transitions", response.context)

    def test_context_has_order(self):
        url = reverse("orders:detail_order", kwargs={"order_id": self.order.id})
        response = self.client.get(url)
        self.assertEqual(response.context["order"].id, self.order.id)

    def test_nonexistent_order_returns_404(self):
        url = reverse("orders:detail_order", kwargs={"order_id": 99999})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_superuser_can_view_any_order(self):
        superuser = UserFactory(is_superuser=True)
        self.client.force_login(superuser)
        url = reverse("orders:detail_order", kwargs={"order_id": self.order.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_blocking_issues_empty_when_order_has_items_and_contact(self):
        """Orden con items y contact info no debe tener blocking issues."""
        OrderContactInfoFactory(order=self.order)
        product = ProductFactory(usage_type="GLOBAL", size_strategy="NONE")
        OrderItemFactory(order=self.order, product=product)

        url = reverse("orders:detail_order", kwargs={"order_id": self.order.id})
        response = self.client.get(url)

        # Sin items → tiene blocking issues de NO_ITEMS y NO_CONTACT_INFO
        # Con items y contacto → no debería tener esos dos
        issue_codes = [i.code for i in response.context["blocking_issues"]]
        self.assertNotIn("NO_ITEMS", issue_codes)
        self.assertNotIn("NO_CONTACT_INFO", issue_codes)


# ===========================================================
# ORDER EDIT
# ===========================================================


@pytest.mark.django_db
class OrderEditViewTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.coach = CoachFactory()
        self.order = OrderFactory(created_by=self.coach, owner_user=self.coach)
        self.client.force_login(self.coach)

    def test_get_returns_200(self):
        url = reverse("orders:edit_order", kwargs={"order_id": self.order.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_other_user_gets_404(self):
        other = CoachFactory()
        self.client.force_login(other)
        url = reverse("orders:edit_order", kwargs={"order_id": self.order.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_design_notes_truncated_to_5000_chars(self):
        url = reverse("orders:edit_order", kwargs={"order_id": self.order.id})
        long_notes = "x" * 6000
        self.client.post(url, {"design_notes": long_notes})
        self.order.refresh_from_db()
        self.assertEqual(len(self.order.design_notes), 5000)


# ===========================================================
# ORDER CONTACT INFO
# ===========================================================


@pytest.mark.django_db
class OrderContactInfoViewTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.coach = CoachFactory()
        self.order = OrderFactory(created_by=self.coach, owner_user=self.coach)
        self.client.force_login(self.coach)

    def test_get_returns_200(self):
        url = reverse("orders:contact_info_order", kwargs={"order_id": self.order.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_post_valid_data_redirects(self):
        url = reverse("orders:contact_info_order", kwargs={"order_id": self.order.id})
        response = self.client.post(
            url,
            {
                "contact_name": "Juan Pérez",
                "contact_phone": "5512345678",
                "contact_email": "juan@test.com",
                "shipping_address_line": "Calle 123",
                "shipping_city": "CDMX",
                "shipping_postal_code": "06600",
            },
        )
        self.assertEqual(response.status_code, 302)

    def test_post_saves_contact_info(self):
        url = reverse("orders:contact_info_order", kwargs={"order_id": self.order.id})
        self.client.post(
            url,
            {
                "contact_name": "Juan Pérez",
                "contact_phone": "5512345678",
                "contact_email": "juan@test.com",
                "shipping_address_line": "Calle 123",
                "shipping_city": "CDMX",
                "shipping_postal_code": "06600",
            },
        )
        self.order.refresh_from_db()
        self.assertTrue(self.order.has_contact_info())
        self.assertEqual(self.order.contact_info.contact_name, "Juan Pérez")

    def test_cannot_edit_contact_info_of_closed_order(self):
        # Crear contact_info cerrado
        contact = OrderContactInfo(
            order=self.order,
            contact_name="Test",
            contact_phone="5512345678",
            contact_email="test@test.com",
            shipping_address_line="Calle 1",
            shipping_city="CDMX",
            shipping_postal_code="06600",
            closed=True,
        )
        # Bypass el save() que impide crear con closed=True
        OrderContactInfo.objects.bulk_create([contact])

        url = reverse("orders:contact_info_order", kwargs={"order_id": self.order.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_other_user_cannot_access_contact_info(self):
        other = CoachFactory()
        self.client.force_login(other)
        url = reverse("orders:contact_info_order", kwargs={"order_id": self.order.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

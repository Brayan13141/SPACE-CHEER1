# orders/tests/test_views_items.py

import pytest
from django.test import TestCase, Client
from django.urls import reverse
from orders.models import OrderItem
from orders.tests.factories import (
    CoachFactory,
    AthleteFactory,
    TeamFactory,
    OrderFactory,
    TeamOrderFactory,
    OrderItemFactory,
    ProductFactory,
    ProductWithMeasurementsFactory,
    UserTeamMembershipFactory,
    OrderItemAthleteFactory,
)


@pytest.mark.django_db
class OrderItemDetailViewTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.coach = CoachFactory()
        self.order = OrderFactory(created_by=self.coach, owner_user=self.coach)
        self.product = ProductFactory(usage_type="GLOBAL", size_strategy="NONE")
        self.item = OrderItemFactory(order=self.order, product=self.product)
        self.client.force_login(self.coach)

    def test_owner_can_view_item(self):
        url = reverse("orders:order_item_detail", kwargs={"item_id": self.item.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_other_user_gets_404(self):
        other = CoachFactory()
        self.client.force_login(other)
        url = reverse("orders:order_item_detail", kwargs={"item_id": self.item.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_unauthenticated_redirects(self):
        self.client.logout()
        url = reverse("orders:order_item_detail", kwargs={"item_id": self.item.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

    def test_context_has_item_and_order(self):
        url = reverse("orders:order_item_detail", kwargs={"item_id": self.item.id})
        response = self.client.get(url)
        self.assertEqual(response.context["item"].id, self.item.id)
        self.assertEqual(response.context["order"].id, self.order.id)


@pytest.mark.django_db
class OrderItemDeleteViewTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.coach = CoachFactory()
        self.order = OrderFactory(created_by=self.coach, owner_user=self.coach)
        self.product = ProductFactory(usage_type="GLOBAL", size_strategy="NONE")
        self.item = OrderItemFactory(order=self.order, product=self.product)
        self.client.force_login(self.coach)

    def test_owner_can_delete_item_from_draft(self):
        url = reverse("orders:order_item_delete", kwargs={"item_id": self.item.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(OrderItem.objects.filter(pk=self.item.id).exists())

    def test_delete_requires_post(self):
        url = reverse("orders:order_item_delete", kwargs={"item_id": self.item.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)

    def test_other_user_cannot_delete_item(self):
        other = CoachFactory()
        self.client.force_login(other)
        url = reverse("orders:order_item_delete", kwargs={"item_id": self.item.id})
        response = self.client.post(url)
        # 404 porque visible_for_user filtra la orden
        self.assertEqual(response.status_code, 404)
        self.assertTrue(OrderItem.objects.filter(pk=self.item.id).exists())

    def test_cannot_delete_item_from_pending_order(self):
        self.order._allow_status_change = True
        self.order.status = "DESIGN_APROVED"
        self.order.save(update_fields=["status"])

        url = reverse("orders:order_item_delete", kwargs={"item_id": self.item.id})
        response = self.client.post(url)
        # PermissionDenied → 403
        self.assertEqual(response.status_code, 403)
        self.assertTrue(OrderItem.objects.filter(pk=self.item.id).exists())

    def test_delete_redirects_to_order_detail(self):
        url = reverse("orders:order_item_delete", kwargs={"item_id": self.item.id})
        response = self.client.post(url)
        expected = reverse("orders:detail_order", kwargs={"order_id": self.order.id})
        self.assertRedirects(response, expected)


@pytest.mark.django_db
class ImportTeamAthletesViewTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.coach = CoachFactory()
        self.team = TeamFactory(coach=self.coach)
        self.order = OrderFactory(
            order_type="TEAM",
            owner_team=self.team,
            owner_user=None,
            created_by=self.coach,
        )
        self.product = ProductWithMeasurementsFactory(
            usage_type="TEAM_CUSTOM",
            size_strategy="MEASUREMENTS",
        )
        self.item = OrderItemFactory(order=self.order, product=self.product)
        self.client.force_login(self.coach)

    def test_import_requires_post(self):
        url = reverse(
            "orders:item_import_team_athletes", kwargs={"item_id": self.item.id}
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)

    def test_import_creates_athlete_assignments(self):
        athlete = AthleteFactory()
        UserTeamMembershipFactory(
            user=athlete,
            team=self.team,
            role_in_team="ATHLETE",
            status="accepted",
            is_active=True,
        )
        url = reverse(
            "orders:item_import_team_athletes", kwargs={"item_id": self.item.id}
        )
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(self.item.athletes.filter(athlete=athlete).exists())

    def test_import_on_personal_order_fails(self):
        personal_order = OrderFactory(created_by=self.coach, owner_user=self.coach)
        personal_item = OrderItemFactory(order=personal_order, product=self.product)
        url = reverse(
            "orders:item_import_team_athletes", kwargs={"item_id": personal_item.id}
        )
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(personal_item.athletes.exists())

    def test_other_user_cannot_import(self):
        other = CoachFactory()
        self.client.force_login(other)
        url = reverse(
            "orders:item_import_team_athletes", kwargs={"item_id": self.item.id}
        )
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)

# orders/tests/test_views_measurements.py

import pytest
from django.test import TestCase, Client
from django.urls import reverse
from orders.tests.factories import (
    UserFactory,
    CoachFactory,
    AthleteFactory,
    TeamFactory,
    OrderFactory,
    OrderItemFactory,
    ProductWithMeasurementsFactory,
    OrderItemAthleteFactory,
    OrderItemMeasurementFactory,
    ProductMeasurementFieldFactory,
    MeasurementFieldFactory,
    UserTeamMembershipFactory,
    RoleFactory,
)
from orders.models import OrderItemMeasurement


@pytest.mark.django_db
class OrderItemMeasurementsViewTests(TestCase):

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
        self.athlete = AthleteFactory()
        UserTeamMembershipFactory(
            user=self.athlete,
            team=self.team,
            role_in_team="ATHLETE",
            status="accepted",
            is_active=True,
        )
        self.athlete_item = OrderItemAthleteFactory(
            order_item=self.item, athlete=self.athlete
        )
        self.client.force_login(self.coach)

    def test_get_measurements_view_returns_200(self):
        url = reverse(
            "orders:order_item_measurements",
            kwargs={"athlete_item_id": self.athlete_item.id},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_unauthenticated_redirects(self):
        self.client.logout()
        url = reverse(
            "orders:order_item_measurements",
            kwargs={"athlete_item_id": self.athlete_item.id},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

    def test_other_user_gets_403(self):
        other = CoachFactory()
        self.client.force_login(other)
        url = reverse(
            "orders:order_item_measurements",
            kwargs={"athlete_item_id": self.athlete_item.id},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_context_has_athlete_item(self):
        url = reverse(
            "orders:order_item_measurements",
            kwargs={"athlete_item_id": self.athlete_item.id},
        )
        response = self.client.get(url)
        self.assertEqual(response.context["athlete_item"].id, self.athlete_item.id)

    def test_context_has_can_edit_flag(self):
        """can_edit ahora vive en el grid, unica fuente de verdad."""
        url = reverse(
            "orders:order_item_measurements",
            kwargs={"athlete_item_id": self.athlete_item.id},
        )
        response = self.client.get(url)
        self.assertIn("grid", response.context)

    def test_can_edit_true_when_order_is_draft(self):
        url = reverse(
            "orders:order_item_measurements",
            kwargs={"athlete_item_id": self.athlete_item.id},
        )
        response = self.client.get(url)
        self.assertTrue(response.context["grid"].can_edit)

    def test_can_edit_false_when_measurements_locked(self):
        self.order.measurements_locked = True
        self.order.save(update_fields=["measurements_locked"])

        url = reverse(
            "orders:order_item_measurements",
            kwargs={"athlete_item_id": self.athlete_item.id},
        )
        response = self.client.get(url)
        self.assertFalse(response.context["grid"].can_edit)


@pytest.mark.django_db
class ItemMeasurementsAddViewTests(TestCase):

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
        self.field = MeasurementFieldFactory(name="Pecho", slug="pecho_test")
        self.product = ProductWithMeasurementsFactory(
            usage_type="TEAM_CUSTOM",
            size_strategy="MEASUREMENTS",
        )
        self.item = OrderItemFactory(order=self.order, product=self.product)
        self.athlete = AthleteFactory()
        UserTeamMembershipFactory(
            user=self.athlete,
            team=self.team,
            role_in_team="ATHLETE",
            status="accepted",
            is_active=True,
        )
        self.athlete_item = OrderItemAthleteFactory(
            order_item=self.item, athlete=self.athlete
        )
        self.client.force_login(self.coach)

    def _url(self):
        return reverse(
            "orders:item_measurements_grid", kwargs={"item_id": self.item.id}
        )

    def _get_post_data(self):
        """Construye el POST data con los campos del producto.

        El endpoint viejo usaba `field_<id>` sobre un solo atleta; el grid usa
        `m-<athlete_item_id>-<field_id>`, que es lo que permite decidir celda
        por celda si el viewer puede escribirla.
        """
        data = {}
        for pmf in self.product.measurement_fields.select_related("field"):
            data[f"m-{self.athlete_item.id}-{pmf.field.id}"] = "95"
        return data

    def test_add_measurements_requires_login(self):
        self.client.logout()
        response = self.client.post(self._url(), {})
        self.assertEqual(response.status_code, 302)

    def test_add_measurements_saves_values(self):
        response = self.client.post(self._url(), self._get_post_data())
        self.assertEqual(response.status_code, 302)

        # Verificar que se guardaron
        saved = OrderItemMeasurement.objects.filter(athlete_item=self.athlete_item)
        self.assertTrue(saved.exists())

    def test_add_measurements_redirects_to_item_detail(self):
        response = self.client.post(self._url(), self._get_post_data())
        expected = reverse("orders:order_item_detail", kwargs={"item_id": self.item.id})
        self.assertRedirects(response, expected)

    def test_cannot_add_measurements_to_locked_order(self):
        self.order.measurements_locked = True
        self.order.save(update_fields=["measurements_locked"])

        response = self.client.post(self._url(), self._get_post_data())
        # El grid rechaza la escritura de plano en vez de redirigir con mensaje
        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            OrderItemMeasurement.objects.filter(athlete_item=self.athlete_item).exists()
        )

    def test_other_user_cannot_add_measurements(self):
        other = CoachFactory()
        self.client.force_login(other)
        response = self.client.post(self._url(), self._get_post_data())
        self.assertEqual(response.status_code, 403)


@pytest.mark.django_db
class MeasurementLifecycleViewTests(TestCase):
    """Tests para close/reopen/lock desde las views de staff."""

    def setUp(self):
        self.client = Client()
        self.staff = UserFactory(
            is_staff=True, profile_completed=True, roles=[RoleFactory(name="ADMIN")]
        )
        self.coach = CoachFactory()
        self.order = OrderFactory(created_by=self.coach, owner_user=self.coach)
        self.client.force_login(self.staff)

    def test_close_measurements_requires_staff(self):
        self.client.force_login(self.coach)
        url = reverse("orders:close_measurements", kwargs={"order_id": self.order.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)

    def test_close_measurements_closes_order(self):
        url = reverse("orders:close_measurements", kwargs={"order_id": self.order.id})
        self.client.post(url)
        self.order.refresh_from_db()
        self.assertFalse(self.order.measurements_open)

    def test_reopen_measurements_reopens_order(self):
        # Primero cerrar
        self.order.measurements_open = False
        self.order.save(update_fields=["measurements_open"])

        url = reverse("orders:reopen_measurements", kwargs={"order_id": self.order.id})
        self.client.post(url)
        self.order.refresh_from_db()
        self.assertTrue(self.order.measurements_open)

    def test_lock_measurements_locks_order(self):
        url = reverse("orders:lock_measurements", kwargs={"order_id": self.order.id})
        self.client.post(url)
        self.order.refresh_from_db()
        self.assertTrue(self.order.measurements_locked)

    def test_lock_already_locked_is_idempotent(self):
        self.order.measurements_locked = True
        self.order.save(update_fields=["measurements_locked"])

        url = reverse("orders:lock_measurements", kwargs={"order_id": self.order.id})
        response = self.client.post(url)
        # No debe explotar
        self.assertEqual(response.status_code, 302)

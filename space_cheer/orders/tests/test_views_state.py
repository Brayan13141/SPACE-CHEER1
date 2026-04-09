# orders/tests/test_views_state.py

import pytest
from django.test import TestCase, Client
from django.urls import reverse

from orders.models import Order, OrderContactInfo
from orders.tests.factories import (
    UserFactory,
    CoachFactory,
    AthleteFactory,
    TeamFactory,
    OrderFactory,
    TeamOrderFactory,
    OrderContactInfoFactory,
    OrderItemFactory,
    ProductFactory,
    OrderDesignImageFactory,
    ProductWithMeasurementsFactory,
    UserTeamMembershipFactory,
)


def _make_order_submittable(order, coach):
    """
    Helper: deja una orden DRAFT lista para pasar a PENDING.
    - Agrega contact info
    - Agrega un producto GLOBAL simple
    - Agrega freeze_payment_date si el producto requiere diseño
    """
    if not order.has_contact_info():
        OrderContactInfo.objects.create(
            order=order,
            contact_name="Test User",
            contact_phone="5512345678",
            contact_email="test@test.com",
            shipping_address_line="Calle 1",
            shipping_city="CDMX",
            shipping_postal_code="06600",
        )

    product = ProductFactory(
        usage_type="GLOBAL",
        size_strategy="NONE",
        is_configured=True,
    )
    OrderItemFactory(order=order, product=product)


# ===========================================================
# TRANSITION VIEW (usuario normal)
# ===========================================================


@pytest.mark.django_db
class TransitionOrderViewTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.coach = CoachFactory()
        self.client.force_login(self.coach)

    def test_transition_requires_post(self):
        """GET a un endpoint de transición → 405."""
        order = OrderFactory(created_by=self.coach, owner_user=self.coach)
        url = reverse(
            "orders:transition",
            kwargs={
                "order_id": order.id,
                "to_status": "CANCELLED",
            },
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)

    def test_transition_requires_login(self):
        self.client.logout()
        order = OrderFactory(created_by=self.coach, owner_user=self.coach)
        url = reverse(
            "orders:transition",
            kwargs={
                "order_id": order.id,
                "to_status": "CANCELLED",
            },
        )
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/", response["Location"])

    def test_cancel_own_draft_order_succeeds(self):
        order = OrderFactory(created_by=self.coach, owner_user=self.coach)
        url = reverse(
            "orders:transition",
            kwargs={
                "order_id": order.id,
                "to_status": "CANCELLED",
            },
        )
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.status, "CANCELLED")

    def test_cancel_redirects_to_order_detail(self):
        order = OrderFactory(created_by=self.coach, owner_user=self.coach)
        url = reverse(
            "orders:transition",
            kwargs={
                "order_id": order.id,
                "to_status": "CANCELLED",
            },
        )
        response = self.client.post(url)
        expected_url = reverse("orders:detail_order", kwargs={"order_id": order.id})
        self.assertRedirects(response, expected_url)

    def test_invalid_status_shows_error_does_not_crash(self):
        order = OrderFactory(created_by=self.coach, owner_user=self.coach)
        url = reverse(
            "orders:transition",
            kwargs={
                "order_id": order.id,
                "to_status": "STATUS_INEXISTENTE",
            },
        )
        # No debe dar 500 — debe redirigir con mensaje de error
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.status, "DRAFT")  # No cambió

    def test_other_user_cannot_cancel_order(self):
        """Otro usuario que no puede ver la orden → 404."""
        other = CoachFactory()
        order = OrderFactory(created_by=self.coach, owner_user=self.coach)

        self.client.force_login(other)
        url = reverse(
            "orders:transition",
            kwargs={
                "order_id": order.id,
                "to_status": "CANCELLED",
            },
        )
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)

    def test_nonexistent_order_returns_404(self):
        url = reverse(
            "orders:transition",
            kwargs={
                "order_id": 99999,
                "to_status": "CANCELLED",
            },
        )
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)

    def test_cannot_transition_delivered_to_any_status(self):
        """Orden DELIVERED no puede transicionar a nada."""
        order = OrderFactory(created_by=self.coach, owner_user=self.coach)
        order._allow_status_change = True
        order.status = "DELIVERED"
        order.closed = True
        order.save(update_fields=["status", "closed"])

        url = reverse(
            "orders:transition",
            kwargs={
                "order_id": order.id,
                "to_status": "CANCELLED",
            },
        )
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)  # redirige con error
        order.refresh_from_db()
        self.assertEqual(order.status, "DELIVERED")  # no cambió

    def test_transition_draft_to_cancelled_creates_log(self):
        from orders.models import OrderLog

        order = OrderFactory(created_by=self.coach, owner_user=self.coach)
        url = reverse(
            "orders:transition",
            kwargs={
                "order_id": order.id,
                "to_status": "CANCELLED",
            },
        )
        self.client.post(url)
        log = OrderLog.objects.filter(
            order=order,
            action="STATUS_CHANGE",
            to_status="CANCELLED",
        ).first()
        self.assertIsNotNone(log)


# ===========================================================
# ADMIN TRANSITION VIEW
# ===========================================================


@pytest.mark.django_db
class AdminTransitionOrderViewTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.staff = UserFactory(is_staff=True)
        self.client.force_login(self.staff)

    def test_admin_transition_requires_post(self):
        coach = CoachFactory()
        order = OrderFactory(created_by=coach, owner_user=coach)
        url = reverse(
            "orders:transition_admin",
            kwargs={
                "order_id": order.id,
                "to_status": "CANCELLED",
            },
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)

    def test_non_staff_cannot_use_admin_transition(self):
        regular_user = CoachFactory()
        self.client.force_login(regular_user)

        coach = CoachFactory()
        order = OrderFactory(created_by=coach, owner_user=coach)
        url = reverse(
            "orders:transition_admin",
            kwargs={
                "order_id": order.id,
                "to_status": "CANCELLED",
            },
        )
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/", response["Location"])

    def test_staff_can_cancel_any_order(self):
        coach = CoachFactory()
        order = OrderFactory(created_by=coach, owner_user=coach)

        url = reverse(
            "orders:transition_admin",
            kwargs={
                "order_id": order.id,
                "to_status": "CANCELLED",
            },
        )
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.status, "CANCELLED")

    def test_admin_transition_redirects_to_admin_detail(self):
        coach = CoachFactory()
        order = OrderFactory(created_by=coach, owner_user=coach)

        url = reverse(
            "orders:transition_admin",
            kwargs={
                "order_id": order.id,
                "to_status": "CANCELLED",
            },
        )
        response = self.client.post(url)
        expected_url = reverse(
            "orders:admin_order_detail", kwargs={"order_id": order.id}
        )
        self.assertRedirects(response, expected_url)

    def test_admin_can_see_all_orders_in_transition(self):
        """Staff puede transicionar órdenes de cualquier usuario."""
        coach1 = CoachFactory()
        coach2 = CoachFactory()
        order1 = OrderFactory(created_by=coach1, owner_user=coach1)
        order2 = OrderFactory(created_by=coach2, owner_user=coach2)

        for order in [order1, order2]:
            url = reverse(
                "orders:transition_admin",
                kwargs={
                    "order_id": order.id,
                    "to_status": "CANCELLED",
                },
            )
            response = self.client.post(url)
            order.refresh_from_db()
            self.assertEqual(
                order.status, "CANCELLED", f"Orden #{order.id} no se canceló"
            )

    def test_invalid_status_does_not_crash(self):
        coach = CoachFactory()
        order = OrderFactory(created_by=coach, owner_user=coach)
        url = reverse(
            "orders:transition_admin",
            kwargs={
                "order_id": order.id,
                "to_status": "ESTADO_INVALIDO",
            },
        )
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.status, "DRAFT")

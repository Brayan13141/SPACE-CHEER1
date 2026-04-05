# orders/tests/test_views_admin.py

import pytest
from django.test import TestCase, Client
from django.urls import reverse
from orders.tests.factories import (
    UserFactory,
    CoachFactory,
    OrderFactory,
    OrderItemFactory,
    ProductFactory,
)


@pytest.mark.django_db
class AdminOrderListViewTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.staff = UserFactory(is_staff=True)
        self.client.force_login(self.staff)

    def test_returns_200_for_staff(self):
        url = reverse("orders:admin_order_list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_non_staff_redirected(self):
        regular = CoachFactory()
        self.client.force_login(regular)
        url = reverse("orders:admin_order_list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

    def test_filter_by_status(self):
        coach = CoachFactory()
        draft_order = OrderFactory(created_by=coach, owner_user=coach)
        cancelled_order = OrderFactory(created_by=coach, owner_user=coach)
        cancelled_order._allow_status_change = True
        cancelled_order.status = "CANCELLED"
        cancelled_order.closed = True
        cancelled_order.save(update_fields=["status", "closed"])

        url = reverse("orders:admin_order_list") + "?status=CANCELLED"
        response = self.client.get(url)
        order_ids = [o.id for o in response.context["orders"]]

        self.assertIn(cancelled_order.id, order_ids)
        self.assertNotIn(draft_order.id, order_ids)

    def test_search_by_order_id(self):
        coach = CoachFactory()
        order = OrderFactory(created_by=coach, owner_user=coach)
        url = reverse("orders:admin_order_list") + f"?q={order.id}"
        response = self.client.get(url)
        order_ids = [o.id for o in response.context["orders"]]
        self.assertIn(order.id, order_ids)

    def test_context_has_stats(self):
        url = reverse("orders:admin_order_list")
        response = self.client.get(url)
        self.assertIn("stats", response.context)
        self.assertIn("total", response.context["stats"])

    def test_unauthenticated_redirects(self):
        self.client.logout()
        url = reverse("orders:admin_order_list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)


@pytest.mark.django_db
class AdminOrderDetailViewTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.staff = UserFactory(is_staff=True)
        self.coach = CoachFactory()
        self.order = OrderFactory(created_by=self.coach, owner_user=self.coach)
        self.client.force_login(self.staff)

    def test_returns_200_for_staff(self):
        url = reverse("orders:admin_order_detail", kwargs={"order_id": self.order.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_non_staff_redirected(self):
        self.client.force_login(self.coach)
        url = reverse("orders:admin_order_detail", kwargs={"order_id": self.order.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

    def test_context_has_order_flags(self):
        url = reverse("orders:admin_order_detail", kwargs={"order_id": self.order.id})
        response = self.client.get(url)
        self.assertIn("order_flags", response.context)

    def test_context_has_dates_form(self):
        url = reverse("orders:admin_order_detail", kwargs={"order_id": self.order.id})
        response = self.client.get(url)
        self.assertIn("dates_form", response.context)

    def test_nonexistent_order_returns_404(self):
        url = reverse("orders:admin_order_detail", kwargs={"order_id": 99999})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)


@pytest.mark.django_db
class AdminUpdateDatesViewTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.staff = UserFactory(is_staff=True)
        self.coach = CoachFactory()
        self.order = OrderFactory(created_by=self.coach, owner_user=self.coach)
        self.client.force_login(self.staff)

    def test_update_dates_valid_data(self):
        url = reverse(
            "orders:admin_update_order_dates", kwargs={"order_id": self.order.id}
        )
        response = self.client.post(
            url,
            {
                "measurements_due_date": "2026-06-01",
                "uniform_delivery_date": "2026-07-01",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.order.refresh_from_db()
        self.assertIsNotNone(self.order.measurements_due_date)

    def test_update_dates_invalid_order_shows_error(self):
        url = reverse(
            "orders:admin_update_order_dates", kwargs={"order_id": self.order.id}
        )
        # Fecha de entrega antes de medidas → error de validación del form
        response = self.client.post(
            url,
            {
                "measurements_due_date": "2026-07-01",
                "uniform_delivery_date": "2026-06-01",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.order.refresh_from_db()
        # No debe haber guardado
        self.assertIsNone(self.order.measurements_due_date)

    def test_requires_post(self):
        url = reverse(
            "orders:admin_update_order_dates", kwargs={"order_id": self.order.id}
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)

    def test_non_staff_redirected(self):
        self.client.force_login(self.coach)
        url = reverse(
            "orders:admin_update_order_dates", kwargs={"order_id": self.order.id}
        )
        response = self.client.post(url, {})
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/", response["Location"])


@pytest.mark.django_db
class AdminUploadDesignViewTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.staff = UserFactory(is_staff=True)
        self.coach = CoachFactory()
        self.order = OrderFactory(created_by=self.coach, owner_user=self.coach)
        self.client.force_login(self.staff)

    def _make_image(self, name="test.jpg"):
        from django.core.files.uploadedfile import SimpleUploadedFile

        return SimpleUploadedFile(
            name,
            b"\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x00\xff\x00,"
            b"\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x00;",
            content_type="image/jpeg",
        )

    def test_upload_design_requires_staff(self):
        self.client.force_login(self.coach)
        url = reverse("orders:admin_upload_design", kwargs={"order_id": self.order.id})
        response = self.client.post(url, {"image": self._make_image()})
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/", response["Location"])

    def test_upload_design_without_image_shows_error(self):
        url = reverse("orders:admin_upload_design", kwargs={"order_id": self.order.id})
        response = self.client.post(url, {})
        self.assertEqual(response.status_code, 302)
        # No se creó imagen
        self.assertEqual(self.order.design_images.count(), 0)

    def test_upload_design_invalid_type_rejected(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        pdf_file = SimpleUploadedFile(
            "doc.pdf", b"fake pdf content", content_type="application/pdf"
        )
        url = reverse("orders:admin_upload_design", kwargs={"order_id": self.order.id})
        response = self.client.post(url, {"image": pdf_file})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.order.design_images.count(), 0)

    def test_upload_design_creates_image(self):
        url = reverse("orders:admin_upload_design", kwargs={"order_id": self.order.id})
        response = self.client.post(
            url,
            {
                "image": self._make_image(),
                "is_final": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.order.design_images.count(), 1)
        self.assertTrue(self.order.design_images.filter(is_final=True).exists())

    def test_upload_second_final_design_shows_error(self):
        from orders.models import OrderDesignImage

        # Crear primer diseño final
        OrderDesignImage.objects.create(
            order=self.order,
            image=self._make_image("first.jpg"),
            uploaded_by=self.staff,
            is_final=True,
        )
        url = reverse("orders:admin_upload_design", kwargs={"order_id": self.order.id})
        # Intentar subir segundo final
        response = self.client.post(
            url,
            {
                "image": self._make_image("second.jpg"),
                "is_final": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        # Solo debe existir 1 imagen final
        self.assertEqual(self.order.design_images.filter(is_final=True).count(), 1)

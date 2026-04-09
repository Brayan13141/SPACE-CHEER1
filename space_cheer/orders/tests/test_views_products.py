# orders/tests/test_views_products.py

import pytest
from django.test import TestCase, Client
from django.urls import reverse
from orders.tests.factories import (
    CoachFactory,
    OrderFactory,
    ProductFactory,
    ProductWithSizesFactory,
)
from django.conf import settings
from orders.models import OrderItem
from products.models import Product


@pytest.mark.django_db
class OrderAddProductViewTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.coach = CoachFactory()
        self.order = OrderFactory(created_by=self.coach, owner_user=self.coach)
        self.client.force_login(self.coach)

    def test_get_returns_200(self):
        url = reverse(
            "orders:add_item_product_order", kwargs={"order_id": self.order.id}
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_other_user_gets_404(self):
        other = CoachFactory()
        self.client.force_login(other)
        url = reverse(
            "orders:add_item_product_order", kwargs={"order_id": self.order.id}
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_add_global_product_creates_item(self):
        product = ProductFactory(
            usage_type="GLOBAL",
            size_strategy="NONE",
            is_configured=True,
        )
        url = reverse(
            "orders:add_item_product_order", kwargs={"order_id": self.order.id}
        )
        response = self.client.post(
            url,
            {
                "product_id": product.id,
                "quantity": 1,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            OrderItem.objects.filter(order=self.order, product=product).exists()
        )

    def test_add_product_with_size_requires_variant(self):
        product = ProductWithSizesFactory(
            usage_type="GLOBAL",
            size_strategy="STANDARD",
            is_configured=True,
        )
        url = reverse(
            "orders:add_item_product_order", kwargs={"order_id": self.order.id}
        )
        # Sin size_variant → debe fallar
        response = self.client.post(
            url,
            {
                "product_id": product.id,
                "quantity": 1,
            },
        )
        # Redirige con error, no crea item
        self.assertFalse(
            OrderItem.objects.filter(order=self.order, product=product).exists()
        )

    def test_cannot_post_if_order_not_editable(self):
        self.order.status = "COMPLETED"
        self.order.closed = True
        self.order.save(update_fields=["status", "closed"])

        product = ProductFactory(
            usage_type="GLOBAL",
            size_strategy="NONE",
            is_configured=True,
        )

        url = reverse(
            "orders:add_item_product_order", kwargs={"order_id": self.order.id}
        )

        response = self.client.post(
            url,
            {"product_id": product.id, "quantity": 1},
        )

        self.assertFalse(
            OrderItem.objects.filter(order=self.order, product=product).exists()
        )

    def test_add_product_with_size_and_variant_creates_item(self):
        product = ProductWithSizesFactory(
            usage_type="GLOBAL",
            size_strategy="STANDARD",
            is_configured=True,
        )
        variant = product.size_variants.first()
        url = reverse(
            "orders:add_item_product_order", kwargs={"order_id": self.order.id}
        )
        self.client.post(
            url,
            {
                "product_id": product.id,
                "quantity": 1,
                "size_variant": variant.id,
            },
        )
        self.assertTrue(
            OrderItem.objects.filter(
                order=self.order, product=product, size_variant=variant
            ).exists()
        )

    def test_context_has_products(self):
        url = reverse(
            "orders:add_item_product_order", kwargs={"order_id": self.order.id}
        )
        response = self.client.get(url)
        self.assertIn("products", response.context)

    def test_context_has_seasons(self):
        url = reverse(
            "orders:add_item_product_order", kwargs={"order_id": self.order.id}
        )
        response = self.client.get(url)
        self.assertIn("seasons", response.context)

    def test_cannot_add_to_non_draft_order(self):
        self.order._allow_status_change = True
        self.order.status = "COMPLETED"
        self.order.closed = True  # opcional pero más seguro
        self.order.save(update_fields=["status", "closed"])

        url = reverse(
            "orders:add_item_product_order", kwargs={"order_id": self.order.id}
        )
        response = self.client.get(url)
        # Redirige con error — la orden no es editable
        self.assertEqual(response.status_code, 302)

    def test_invalid_quantity_does_not_create_item(self):
        product = ProductFactory(
            usage_type="GLOBAL",
            size_strategy="NONE",
            is_configured=True,
        )
        url = reverse(
            "orders:add_item_product_order", kwargs={"order_id": self.order.id}
        )
        self.client.post(
            url,
            {
                "product_id": product.id,
                "quantity": "no_es_numero",
            },
        )

        self.assertFalse(
            OrderItem.objects.filter(order=self.order, product=product).exists()
        )

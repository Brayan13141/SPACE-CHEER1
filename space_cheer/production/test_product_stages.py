from django.test import TestCase, Client
from django.urls import reverse

from orders.tests.factories import ProductFactory, UserFactory
from production.models import ProductionStage, ProductStageConfig


def make_admin_client():
    user = UserFactory(is_superuser=True, is_staff=True, profile_completed=True)
    client = Client()
    client.force_login(user)
    return client


def make_stage(name="Diseño", slug="diseno", order=1):
    return ProductionStage.objects.create(name=name, slug=slug, display_order=order)


class ProductStageConfigViewTests(TestCase):

    def setUp(self):
        self.client = make_admin_client()
        self.product = ProductFactory()
        self.stage = make_stage()
        self.url = reverse("products:product_detail", kwargs={"product_id": self.product.pk})

    # ── GET ──────────────────────────────────────────────────────────────────

    def test_product_detail_includes_stages_in_context(self):
        """product_detail debe incluir stage_configs y available_stages en el contexto"""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("stage_configs", response.context)
        self.assertIn("available_stages", response.context)

    def test_available_stages_excludes_already_configured(self):
        """available_stages no debe incluir etapas ya configuradas"""
        ProductStageConfig.objects.create(
            product=self.product, stage=self.stage, display_order=1
        )
        response = self.client.get(self.url)
        available = list(response.context["available_stages"])
        self.assertNotIn(self.stage, available)

    # ── add_stage ────────────────────────────────────────────────────────────

    def test_add_stage_creates_product_stage_config(self):
        """POST action=add_stage crea un ProductStageConfig"""
        self.client.post(self.url, {
            "action": "add_stage",
            "stage_id": self.stage.pk,
            "stage_order": 1,
        })
        self.assertTrue(
            ProductStageConfig.objects.filter(
                product=self.product, stage=self.stage
            ).exists()
        )

    def test_add_stage_sets_display_order(self):
        """POST action=add_stage respeta el display_order enviado"""
        self.client.post(self.url, {
            "action": "add_stage",
            "stage_id": self.stage.pk,
            "stage_order": 3,
        })
        config = ProductStageConfig.objects.get(product=self.product, stage=self.stage)
        self.assertEqual(config.display_order, 3)

    def test_add_stage_redirects_after_post(self):
        response = self.client.post(self.url, {
            "action": "add_stage",
            "stage_id": self.stage.pk,
            "stage_order": 1,
        })
        self.assertEqual(response.status_code, 302)

    def test_add_stage_duplicate_shows_warning_not_duplicate(self):
        """Intentar añadir la misma etapa dos veces no crea duplicado"""
        ProductStageConfig.objects.create(
            product=self.product, stage=self.stage, display_order=1
        )
        self.client.post(self.url, {
            "action": "add_stage",
            "stage_id": self.stage.pk,
            "stage_order": 2,
        })
        count = ProductStageConfig.objects.filter(
            product=self.product, stage=self.stage
        ).count()
        self.assertEqual(count, 1)

    def test_add_stage_without_stage_id_does_not_create(self):
        """POST action=add_stage sin stage_id no crea nada"""
        self.client.post(self.url, {
            "action": "add_stage",
            "stage_id": "",
            "stage_order": 1,
        })
        self.assertFalse(
            ProductStageConfig.objects.filter(product=self.product).exists()
        )

    # ── remove_stage ─────────────────────────────────────────────────────────

    def test_remove_stage_deletes_product_stage_config(self):
        """POST action=remove_stage elimina el ProductStageConfig"""
        ProductStageConfig.objects.create(
            product=self.product, stage=self.stage, display_order=1
        )
        self.client.post(self.url, {
            "action": "remove_stage",
            "stage_id": self.stage.pk,
        })
        self.assertFalse(
            ProductStageConfig.objects.filter(
                product=self.product, stage=self.stage
            ).exists()
        )

    def test_remove_stage_redirects_after_post(self):
        ProductStageConfig.objects.create(
            product=self.product, stage=self.stage, display_order=1
        )
        response = self.client.post(self.url, {
            "action": "remove_stage",
            "stage_id": self.stage.pk,
        })
        self.assertEqual(response.status_code, 302)

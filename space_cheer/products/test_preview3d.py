import shutil
import struct
import tempfile

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

User = get_user_model()

TEST_MEDIA = tempfile.mkdtemp(prefix="sc_test_media3d_")


def make_glb(name="modelo.glb", size=None):
    """GLB mínimo válido: header 'glTF' + versión 2 + longitud."""
    payload = struct.pack("<4sII", b"glTF", 2, 12)
    if size:
        payload += b"\x00" * (size - len(payload))
    return SimpleUploadedFile(name, payload, content_type="model/gltf-binary")


@override_settings(MEDIA_ROOT=TEST_MEDIA)
class GlbValidatorTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEST_MEDIA, ignore_errors=True)

    def test_valid_glb_passes(self):
        from core.file_utils import validate_glb_magic

        validate_glb_magic(make_glb())  # no debe lanzar

    def test_renamed_file_rejected(self):
        from core.file_utils import validate_glb_magic

        fake = SimpleUploadedFile("falso.glb", b"MZ\x90\x00 exe disfrazado")
        with self.assertRaises(ValidationError):
            validate_glb_magic(fake)

    def test_oversize_rejected(self):
        from core.file_utils import validate_glb_max_15mb

        big = make_glb(size=16 * 1024 * 1024)
        with self.assertRaises(ValidationError):
            validate_glb_max_15mb(big)

    def test_product_accepts_model_3d(self):
        from products.models import Product, Season

        season = Season.objects.create(name="Test 2026")
        product = Product.objects.create(
            name="Uniforme 3D",
            product_type="UNIFORM",
            usage_type="GLOBAL",
            size_strategy="NONE",
            season=season,
            base_price="100.00",
            model_3d=make_glb(),
        )
        self.assertTrue(product.model_3d.name.startswith("products/models3d/"))


@override_settings(MEDIA_ROOT=TEST_MEDIA)
class ProductFormModel3DTests(TestCase):
    def _form_data(self):
        from products.models import Season

        season = Season.objects.create(name="Form 2026")
        return {
            "name": "Producto Form",
            "product_type": "UNIFORM",
            "usage_type": "GLOBAL",
            "size_strategy": "NONE",
            "scope": "CATALOG",
            "season": season.pk,
            "base_price": "50.00",
            "is_active": True,
        }

    def test_form_accepts_valid_glb(self):
        from products.forms import ProductForm

        form = ProductForm(self._form_data(), {"model_3d": make_glb()})
        self.assertTrue(form.is_valid(), form.errors)

    def test_form_rejects_fake_glb(self):
        from products.forms import ProductForm

        fake = SimpleUploadedFile("falso.glb", b"no soy un glb")
        form = ProductForm(self._form_data(), {"model_3d": fake})
        self.assertFalse(form.is_valid())
        self.assertIn("model_3d", form.errors)


class FeatureFlagTests(TestCase):
    def test_flag_in_template_context(self):
        user = User.objects.create_user(username="flag_test", password="Test1234!")
        self.client.force_login(user)
        resp = self.client.get("/")
        self.assertIn("preview_3d_enabled", resp.context)


@override_settings(MEDIA_ROOT=TEST_MEDIA)
class ProductDetail3DRenderTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from accounts.models import Role
        from products.models import Product, Season

        cls.user = User.objects.create_user(
            username="render_test", password="Test1234!", profile_completed=True
        )
        admin_role, _ = Role.objects.get_or_create(name="ADMIN")
        cls.user.roles.add(admin_role)
        season = Season.objects.create(name="Render 2026")
        cls.product = Product.objects.create(
            name="Producto Render",
            product_type="UNIFORM",
            usage_type="GLOBAL",
            size_strategy="NONE",
            season=season,
            base_price="10.00",
        )

    def setUp(self):
        self.client.force_login(self.user)

    def test_section_renders_when_flag_on(self):
        resp = self.client.get(f"/products/{self.product.pk}/")
        self.assertContains(resp, "preview3d-container")
        self.assertContains(resp, "JS/vendor/three.min.js")

    @override_settings(PREVIEW_3D_ENABLED=False)
    def test_section_hidden_when_flag_off(self):
        resp = self.client.get(f"/products/{self.product.pk}/")
        self.assertNotContains(resp, "preview3d-container")

    def test_model_url_present_when_product_has_glb(self):
        self.product.model_3d = make_glb()
        self.product.save()
        resp = self.client.get(f"/products/{self.product.pk}/")
        self.assertContains(resp, self.product.model_3d.url)

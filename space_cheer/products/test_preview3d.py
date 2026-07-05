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

import base64
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.test import TestCase, override_settings

User = get_user_model()

# PNG válido de 1x1 px (pasa validate_image_magic)
PNG_1x1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8"
    "z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)

TEST_MEDIA = tempfile.mkdtemp(prefix="sc_test_media_")


def make_png(name="foto.png"):
    return SimpleUploadedFile(name, PNG_1x1, content_type="image/png")


@override_settings(MEDIA_ROOT=TEST_MEDIA)
class SocialBaseTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="bryan_test", email="bryan@test.com", password="Test1234!")
        cls.other = User.objects.create_user(username="otro_test", email="otro@test.com", password="Test1234!")

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEST_MEDIA, ignore_errors=True)


class PostModelTests(SocialBaseTestCase):
    def test_post_ordering_newest_first(self):
        from social.models import Post

        p1 = Post.objects.create(author=self.user, text="primero")
        p2 = Post.objects.create(author=self.user, text="segundo")
        self.assertEqual(list(Post.objects.all()), [p2, p1])

    def test_like_unique_per_user(self):
        from social.models import Post, PostLike

        post = Post.objects.create(author=self.user, text="hola")
        PostLike.objects.create(post=post, user=self.other)
        with self.assertRaises(IntegrityError):
            PostLike.objects.create(post=post, user=self.other)

    def test_repost_cascade_on_original_delete(self):
        from social.models import Post

        original = Post.objects.create(author=self.user, text="original")
        repost = Post.objects.create(author=self.other, text="", shared_post=original)
        original.delete()
        self.assertFalse(Post.objects.filter(pk=repost.pk).exists())

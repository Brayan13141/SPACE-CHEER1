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


class FeedServiceTests(SocialBaseTestCase):
    def test_create_post_requires_text_or_image(self):
        from django.core.exceptions import ValidationError
        from social.services import FeedService

        with self.assertRaises(ValidationError):
            FeedService.create_post(self.user, text="   ", images=[])

    def test_create_post_with_images(self):
        from social.services import FeedService

        post = FeedService.create_post(
            self.user, text="con fotos", images=[make_png("a.png"), make_png("b.png")]
        )
        self.assertEqual(post.images.count(), 2)
        self.assertEqual(post.images.first().order, 0)

    def test_create_post_max_4_images(self):
        from django.core.exceptions import ValidationError
        from social.services import FeedService

        images = [make_png(f"{i}.png") for i in range(5)]
        with self.assertRaises(ValidationError):
            FeedService.create_post(self.user, text="", images=images)

    def test_toggle_like(self):
        from social.models import Post
        from social.services import FeedService

        post = Post.objects.create(author=self.user, text="hola")
        liked, count = FeedService.toggle_like(self.other, post)
        self.assertTrue(liked)
        self.assertEqual(count, 1)
        liked, count = FeedService.toggle_like(self.other, post)
        self.assertFalse(liked)
        self.assertEqual(count, 0)

    def test_repost_of_repost_points_to_original(self):
        from social.models import Post
        from social.services import FeedService

        original = Post.objects.create(author=self.user, text="original")
        repost1 = FeedService.create_repost(self.other, original, text="mira")
        repost2 = FeedService.create_repost(self.user, repost1, text="yo también")
        self.assertEqual(repost2.shared_post_id, original.pk)

    def test_delete_post_permissions(self):
        from django.core.exceptions import PermissionDenied
        from accounts.models import Role
        from social.models import Post
        from social.services import FeedService

        post = Post.objects.create(author=self.user, text="mío")
        with self.assertRaises(PermissionDenied):
            FeedService.delete_post(self.other, post)

        admin_role, _ = Role.objects.get_or_create(name="ADMIN")
        self.other.roles.add(admin_role)
        FeedService.delete_post(self.other, post)  # ADMIN sí puede
        self.assertFalse(Post.objects.filter(pk=post.pk).exists())

    def test_delete_own_post_removes_image_files(self):
        from social.services import FeedService

        post = FeedService.create_post(self.user, text="", images=[make_png("c.png")])
        storage = post.images.first().image.storage
        path = post.images.first().image.name
        self.assertTrue(storage.exists(path))
        FeedService.delete_post(self.user, post)
        self.assertFalse(storage.exists(path))

    def test_add_comment_empty_rejected(self):
        from django.core.exceptions import ValidationError
        from social.models import Post
        from social.services import FeedService

        post = Post.objects.create(author=self.user, text="hola")
        with self.assertRaises(ValidationError):
            FeedService.add_comment(self.other, post, "  ")

    def test_feed_queryset_annotates(self):
        from social.models import Post
        from social.services import FeedService

        post = Post.objects.create(author=self.user, text="hola")
        FeedService.toggle_like(self.other, post)
        FeedService.add_comment(self.other, post, "buen post")
        FeedService.add_comment(self.other, post, "excelente post")

        row = FeedService.feed_queryset(self.other).get(pk=post.pk)
        self.assertEqual(row.like_count, 1)
        self.assertEqual(row.comment_count, 2)
        self.assertTrue(row.liked_by_me)
        self.assertEqual(len(row.recent_comments), 2)
        # Verificar que los comentarios están ordenados por más reciente primero
        self.assertEqual(row.recent_comments[0].text, "excelente post")
        self.assertEqual(row.recent_comments[1].text, "buen post")

    def test_create_post_invalid_second_image_leaves_no_orphans(self):
        from django.core.exceptions import ValidationError
        from pathlib import Path
        from django.core.files.storage import default_storage
        from social.models import Post, PostImage
        from social.services import FeedService

        fake = SimpleUploadedFile("falsa.png", b"no soy una imagen")
        with self.assertRaises(ValidationError):
            FeedService.create_post(
                self.user, text="", images=[make_png("ok.png"), fake]
            )
        self.assertEqual(Post.objects.count(), 0)
        self.assertEqual(PostImage.objects.count(), 0)
        # Ningún archivo huérfano escrito en storage
        media_social = Path(default_storage.location) / "social"
        leftover = list(media_social.rglob("ok*.png")) if media_social.exists() else []
        self.assertEqual(leftover, [])


class RankingServiceTests(SocialBaseTestCase):
    def test_ranking_counts_and_sort(self):
        from teams.models import Team, UserTeamMembership
        from social.models import Post
        from social.services import RankingService

        # Create a coach for teams
        coach = User.objects.create_user(username="coach_test", email="coach@test.com", password="Test1234!")

        team_a = Team.objects.create(name="Stars A", coach=coach, city="CDMX", phone="5555551234")
        team_b = Team.objects.create(name="Stars B", coach=coach, city="CDMX", phone="5555551235")
        UserTeamMembership.objects.create(
            user=self.user, team=team_a, status="accepted", is_active=True
        )
        UserTeamMembership.objects.create(
            user=self.other, team=team_a, status="accepted", is_active=True
        )
        UserTeamMembership.objects.create(
            user=self.user, team=team_b, status="inactive", is_active=False
        )
        Post.objects.create(author=self.user, text="post de miembro activo")

        ranking = list(RankingService.team_ranking(sort_key="athletes"))
        self.assertEqual(ranking[0].pk, team_a.pk)
        self.assertEqual(ranking[0].num_athletes, 2)
        self.assertEqual(ranking[0].num_posts, 1)
        self.assertEqual(ranking[0].num_competitions, 0)
        # team_b no cuenta la membresía inactiva
        row_b = next(t for t in ranking if t.pk == team_b.pk)
        self.assertEqual(row_b.num_athletes, 0)
        self.assertEqual(row_b.num_posts, 0)

    def test_ranking_invalid_sort_falls_back(self):
        from social.services import RankingService

        # No debe lanzar error con sort_key basura
        list(RankingService.team_ranking(sort_key="'; DROP TABLE--"))

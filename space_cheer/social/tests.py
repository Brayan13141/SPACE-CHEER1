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

    def test_toggle_like_defaults_to_applause_reaction(self):
        from social.models import Post, PostLike
        from social.services import FeedService

        post = Post.objects.create(author=self.user, text="hola")
        FeedService.toggle_like(self.other, post)
        like = PostLike.objects.get(post=post, user=self.other)
        self.assertEqual(like.reaction, PostLike.Reaction.APPLAUSE)

    def test_reacting_with_different_type_switches_it(self):
        from social.models import Post, PostLike
        from social.services import FeedService

        post = Post.objects.create(author=self.user, text="hola")
        FeedService.toggle_like(self.other, post, reaction=PostLike.Reaction.APPLAUSE)
        liked, count = FeedService.toggle_like(
            self.other, post, reaction=PostLike.Reaction.FIRE
        )
        self.assertTrue(liked)
        self.assertEqual(count, 1)
        like = PostLike.objects.get(post=post, user=self.other)
        self.assertEqual(like.reaction, PostLike.Reaction.FIRE)

    def test_reacting_with_same_type_twice_removes_it(self):
        from social.models import Post, PostLike
        from social.services import FeedService

        post = Post.objects.create(author=self.user, text="hola")
        FeedService.toggle_like(self.other, post, reaction=PostLike.Reaction.FIRE)
        liked, count = FeedService.toggle_like(
            self.other, post, reaction=PostLike.Reaction.FIRE
        )
        self.assertFalse(liked)
        self.assertEqual(count, 0)
        self.assertFalse(PostLike.objects.filter(post=post, user=self.other).exists())

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


class FeedViewTests(SocialBaseTestCase):
    def setUp(self):
        self.client.force_login(self.user)

    def test_feed_requires_login(self):
        self.client.logout()
        resp = self.client.get("/social/")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/accounts/login/", resp["Location"])

    def test_feed_renders(self):
        from social.models import Post

        Post.objects.create(author=self.user, text="hola feed")
        resp = self.client.get("/social/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "hola feed")

    def test_post_create_prg(self):
        resp = self.client.post("/social/post/nuevo/", {"text": "nuevo post"})
        self.assertRedirects(resp, "/social/")
        from social.models import Post

        self.assertTrue(Post.objects.filter(text="nuevo post").exists())

    def test_post_create_empty_shows_error(self):
        resp = self.client.post("/social/post/nuevo/", {"text": "  "}, follow=True)
        self.assertEqual(resp.status_code, 200)
        from social.models import Post

        self.assertEqual(Post.objects.count(), 0)

    def test_like_toggle_json(self):
        from social.models import Post

        post = Post.objects.create(author=self.other, text="likeame")
        resp = self.client.post(f"/social/post/{post.pk}/like/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["liked"])
        self.assertEqual(data["like_count"], 1)

    def test_comment_create_redirects_back(self):
        from social.models import Post

        post = Post.objects.create(author=self.other, text="comenta")
        resp = self.client.post(
            f"/social/post/{post.pk}/comentar/",
            {"text": "buen post", "next": f"/social/post/{post.pk}/"},
        )
        self.assertRedirects(resp, f"/social/post/{post.pk}/")
        self.assertEqual(post.comments.count(), 1)

    def test_comment_next_open_redirect_blocked(self):
        from social.models import Post

        post = Post.objects.create(author=self.other, text="x")
        resp = self.client.post(
            f"/social/post/{post.pk}/comentar/",
            {"text": "hola", "next": "https://evil.com/"},
        )
        self.assertRedirects(resp, "/social/")

    def test_repost_create(self):
        from social.models import Post

        post = Post.objects.create(author=self.other, text="original")
        resp = self.client.post(
            f"/social/post/{post.pk}/compartir/", {"text": "míralo"}
        )
        self.assertRedirects(resp, "/social/")
        self.assertTrue(
            Post.objects.filter(author=self.user, shared_post=post).exists()
        )

    def test_post_delete_forbidden_for_stranger(self):
        from social.models import Post

        post = Post.objects.create(author=self.other, text="ajeno")
        resp = self.client.post(f"/social/post/{post.pk}/eliminar/")
        self.assertEqual(resp.status_code, 403)

    def test_ranking_renders(self):
        resp = self.client.get("/social/ranking/")
        self.assertEqual(resp.status_code, 200)
        resp = self.client.get("/social/ranking/?sort=posts")
        self.assertEqual(resp.status_code, 200)

    def test_admin_role_sees_delete_button(self):
        from accounts.models import Role
        from social.models import Post

        post = Post.objects.create(author=self.other, text="post ajeno")
        admin_role, _ = Role.objects.get_or_create(name="ADMIN")
        self.user.roles.add(admin_role)
        resp = self.client.get("/social/")
        self.assertContains(resp, f"/social/post/{post.pk}/eliminar/")

    def test_like_toggle_switch_reaction_via_view(self):
        from social.models import Post

        post = Post.objects.create(author=self.other, text="reacciona")
        self.client.post(f"/social/post/{post.pk}/like/", {"reaction": "FIRE"})
        resp = self.client.post(f"/social/post/{post.pk}/like/", {"reaction": "STAR"})
        data = resp.json()
        self.assertTrue(data["liked"])
        self.assertEqual(data["reaction"], "STAR")
        self.assertEqual(data["like_count"], 1)

    def test_like_toggle_rejects_unknown_reaction(self):
        from social.models import Post, PostLike

        post = Post.objects.create(author=self.other, text="reacciona")
        resp = self.client.post(
            f"/social/post/{post.pk}/like/", {"reaction": "NOT_A_REACTION"}
        )
        self.assertEqual(resp.status_code, 200)
        like = PostLike.objects.get(post=post, user=self.user)
        self.assertEqual(like.reaction, PostLike.Reaction.APPLAUSE)

    def test_feed_ajax_fragment_omits_page_chrome(self):
        from social.models import Post

        Post.objects.create(author=self.user, text="fragmento")
        resp = self.client.get("/social/", HTTP_X_REQUESTED_WITH="fetch")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "fragmento")
        self.assertNotContains(resp, "sc-v2-composer")

    def test_feed_renders_without_teams_or_tournament(self):
        """Usuario sin equipos: sugerencias/historias/torneo vacíos, sin 500."""
        resp = self.client.get("/social/")
        self.assertEqual(resp.status_code, 200)


class SeedWelcomePostsCommandTests(SocialBaseTestCase):
    def test_creates_posts_authored_by_admin(self):
        from django.core.management import call_command
        from accounts.models import Role
        from social.models import Post

        admin_role, _ = Role.objects.get_or_create(name="ADMIN")
        self.user.roles.add(admin_role)

        call_command("seed_welcome_posts")

        self.assertGreater(Post.objects.filter(author=self.user).count(), 0)

    def test_is_idempotent(self):
        from django.core.management import call_command
        from accounts.models import Role
        from social.models import Post

        admin_role, _ = Role.objects.get_or_create(name="ADMIN")
        self.user.roles.add(admin_role)

        call_command("seed_welcome_posts")
        first_count = Post.objects.count()
        call_command("seed_welcome_posts")
        self.assertEqual(Post.objects.count(), first_count)

    def test_dry_run_creates_nothing(self):
        from django.core.management import call_command
        from accounts.models import Role
        from social.models import Post

        admin_role, _ = Role.objects.get_or_create(name="ADMIN")
        self.user.roles.add(admin_role)

        call_command("seed_welcome_posts", "--dry-run")
        self.assertEqual(Post.objects.count(), 0)

    def test_raises_without_admin_user(self):
        from django.core.management import call_command, CommandError

        with self.assertRaises(CommandError):
            call_command("seed_welcome_posts")

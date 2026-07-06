"""Tests del Portal Social (perfiles, visibilidad, notificaciones, configuración)."""
import pytest
from django.contrib.auth import get_user_model

from accounts.models import Notification
from social.models import SocialProfile
from social.profile_services import SocialProfileService

User = get_user_model()


def make_user(username, **kwargs):
    return User.objects.create_user(
        username=username, password="Test1234!", email=f"{username}@test.com", **kwargs
    )


@pytest.mark.django_db
class TestSocialProfile:
    def test_for_user_crea_perfil_con_defaults(self):
        user = make_user("bryan")
        profile = SocialProfileService.for_user(user)
        assert profile.pk is not None
        assert profile.profile_visibility == SocialProfile.Visibility.PLATFORM
        assert profile.posts_visibility == SocialProfile.Visibility.PLATFORM
        assert profile.hide_activity is False
        assert profile.feed_density == SocialProfile.FeedDensity.COMFORTABLE
        assert profile.notify_likes and profile.notify_comments and profile.notify_reposts

    def test_for_user_es_idempotente(self):
        user = make_user("bryan")
        p1 = SocialProfileService.for_user(user)
        p2 = SocialProfileService.for_user(user)
        assert p1.pk == p2.pk
        assert SocialProfile.objects.filter(user=user).count() == 1


@pytest.mark.django_db
class TestNotificationModel:
    def test_tipos_sociales_y_url(self):
        user = make_user("bryan")
        n = Notification.objects.create(
            user=user,
            title="A coach_test le gustó tu publicación",
            notification_type=Notification.NotificationType.SOCIAL_LIKE,
            url="/social/post/1/",
        )
        assert n.url == "/social/post/1/"
        assert n.notification_type.startswith("SOCIAL_")
        assert Notification.NotificationType.SOCIAL_COMMENT in Notification.NotificationType.values
        assert Notification.NotificationType.SOCIAL_REPOST in Notification.NotificationType.values


from accounts.models import Role
from social.models import Post
from social.profile_services import SocialVisibilityService
from social.services import FeedService
from teams.models import Team, UserTeamMembership


def make_team(coach, name="Stars"):
    return Team.objects.create(name=name, coach=coach, city="León", phone="4771234567")


def join(user, team):
    return UserTeamMembership.objects.create(
        user=user, team=team, is_active=True, status="accepted"
    )


def make_admin(username="admin"):
    user = make_user(username)
    role, _ = Role.objects.get_or_create(name="ADMIN")
    user.roles.add(role)
    return user


@pytest.mark.django_db
class TestVisibleForViewer:
    def setup_method(self, method):
        self.coach = None  # se crea por test

    def _setup_world(self):
        """author y teammate comparten equipo; outsider no. Devuelve (author, teammate, outsider, post)."""
        author = make_user("author")
        teammate = make_user("teammate")
        outsider = make_user("outsider")
        team = make_team(coach=author)
        join(author, team)
        join(teammate, team)
        post = Post.objects.create(author=author, text="hola espacio")
        return author, teammate, outsider, post

    def test_platform_visible_para_todos(self):
        author, teammate, outsider, post = self._setup_world()
        # Sin SocialProfile explícito (default PLATFORM implícito)
        assert post in Post.objects.visible_for_viewer(outsider)
        assert post in Post.objects.visible_for_viewer(teammate)

    def test_team_visible_solo_para_companeros_activos(self):
        author, teammate, outsider, post = self._setup_world()
        profile = SocialProfileService.for_user(author)
        profile.posts_visibility = SocialProfile.Visibility.TEAM
        profile.save()
        assert post in Post.objects.visible_for_viewer(teammate)
        assert post not in Post.objects.visible_for_viewer(outsider)

    def test_team_autor_siempre_ve_lo_suyo(self):
        author, _, _, post = self._setup_world()
        profile = SocialProfileService.for_user(author)
        profile.posts_visibility = SocialProfile.Visibility.TEAM
        profile.save()
        assert post in Post.objects.visible_for_viewer(author)

    def test_team_admin_ve_todo(self):
        author, _, _, post = self._setup_world()
        profile = SocialProfileService.for_user(author)
        profile.posts_visibility = SocialProfile.Visibility.TEAM
        profile.save()
        admin = make_admin()
        assert post in Post.objects.visible_for_viewer(admin)

    def test_team_sin_equipo_activo_solo_autor_y_admin(self):
        author = make_user("solo")
        post = Post.objects.create(author=author, text="sin equipo")
        profile = SocialProfileService.for_user(author)
        profile.posts_visibility = SocialProfile.Visibility.TEAM
        profile.save()
        other = make_user("otro")
        assert post not in Post.objects.visible_for_viewer(other)
        assert post in Post.objects.visible_for_viewer(author)
        assert post in Post.objects.visible_for_viewer(make_admin())

    def test_membresia_inactiva_no_cuenta(self):
        author, teammate, _, post = self._setup_world()
        profile = SocialProfileService.for_user(author)
        profile.posts_visibility = SocialProfile.Visibility.TEAM
        profile.save()
        UserTeamMembership.objects.filter(user=teammate).update(is_active=False)
        assert post not in Post.objects.visible_for_viewer(teammate)

    def test_autor_inactivo_excluido_del_feed(self):
        author, teammate, _, post = self._setup_world()
        author.is_active = False
        author.save()
        assert post not in Post.objects.visible_for_viewer(teammate)

    def test_feed_queryset_anota_shared_visible(self):
        author, teammate, outsider, post = self._setup_world()
        profile = SocialProfileService.for_user(author)
        profile.posts_visibility = SocialProfile.Visibility.TEAM
        profile.save()
        repost = FeedService.create_repost(teammate, post, "miren esto")
        # outsider ve el repost (teammate es PLATFORM) pero NO el original embebido
        feed_outsider = {p.pk: p for p in FeedService.feed_queryset(outsider)}
        assert repost.pk in feed_outsider
        assert post.pk not in feed_outsider
        assert feed_outsider[repost.pk].shared_visible is False
        # teammate sí ve el original embebido
        feed_teammate = {p.pk: p for p in FeedService.feed_queryset(teammate)}
        assert feed_teammate[repost.pk].shared_visible is True


@pytest.mark.django_db
class TestSocialVisibilityService:
    def test_can_view_profile_platform(self):
        owner = make_user("owner")
        viewer = make_user("viewer")
        assert SocialVisibilityService.can_view_profile(viewer, owner) is True

    def test_can_view_profile_team(self):
        owner = make_user("owner")
        viewer = make_user("viewer")
        outsider = make_user("outsider2")
        team = make_team(coach=owner)
        join(owner, team)
        join(viewer, team)
        profile = SocialProfileService.for_user(owner)
        profile.profile_visibility = SocialProfile.Visibility.TEAM
        profile.save()
        assert SocialVisibilityService.can_view_profile(viewer, owner) is True
        assert SocialVisibilityService.can_view_profile(outsider, owner) is False
        assert SocialVisibilityService.can_view_profile(owner, owner) is True
        assert SocialVisibilityService.can_view_profile(make_admin("adm2"), owner) is True

    def test_can_view_profile_usuario_inactivo(self):
        owner = make_user("owner")
        owner.is_active = False
        owner.save()
        assert SocialVisibilityService.can_view_profile(make_user("v2"), owner) is False


from social.services import FeedService as FS


@pytest.mark.django_db
class TestSocialNotifications:
    def _pair(self):
        author = make_user("author")
        fan = make_user("fan")
        post = Post.objects.create(author=author, text="post con fans")
        return author, fan, post

    def test_like_crea_notificacion(self):
        author, fan, post = self._pair()
        FS.toggle_like(fan, post)
        n = Notification.objects.get(user=author)
        assert n.notification_type == Notification.NotificationType.SOCIAL_LIKE
        assert n.url == f"/social/post/{post.pk}/"
        assert n.read is False

    def test_unlike_no_crea_segunda_notificacion(self):
        author, fan, post = self._pair()
        FS.toggle_like(fan, post)   # like
        FS.toggle_like(fan, post)   # unlike
        assert Notification.objects.filter(user=author).count() == 1

    def test_no_autonotificacion(self):
        author, _, post = self._pair()
        FS.toggle_like(author, post)
        FS.add_comment(author, post, "mi propio comentario")
        assert Notification.objects.filter(user=author).count() == 0

    def test_toggle_apagado_no_crea(self):
        author, fan, post = self._pair()
        profile = SocialProfileService.for_user(author)
        profile.notify_likes = False
        profile.save()
        FS.toggle_like(fan, post)
        assert Notification.objects.filter(user=author).count() == 0

    def test_comentario_y_repost_notifican(self):
        author, fan, post = self._pair()
        FS.add_comment(fan, post, "buen post")
        FS.create_repost(fan, post, "")
        tipos = set(
            Notification.objects.filter(user=author).values_list(
                "notification_type", flat=True
            )
        )
        assert tipos == {"SOCIAL_COMMENT", "SOCIAL_REPOST"}

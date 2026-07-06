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


@pytest.mark.django_db
class TestContadoresCampana:
    def test_contadores_separados(self, client):
        user = make_user("bryan")
        Notification.objects.create(
            user=user, title="tarea", notification_type="TASK_ASSIGNED"
        )
        Notification.objects.create(
            user=user, title="like", notification_type="SOCIAL_LIKE"
        )
        Notification.objects.create(
            user=user, title="like leído", notification_type="SOCIAL_LIKE", read=True
        )
        client.force_login(user)
        response = client.get("/social/")
        assert response.context["unread_notifications_count"] == 1
        assert response.context["unread_social_count"] == 1


@pytest.mark.django_db
class TestNotificationViews:
    def _login_with_notifications(self, client):
        user = make_user("bryan")
        other = make_user("fan2")
        n1 = Notification.objects.create(
            user=user, title="like 1", notification_type="SOCIAL_LIKE", url="/social/post/1/"
        )
        Notification.objects.create(
            user=user, title="tarea", notification_type="TASK_ASSIGNED"
        )
        Notification.objects.create(
            user=other, title="ajeno", notification_type="SOCIAL_LIKE"
        )
        client.force_login(user)
        return user, n1

    def test_lista_solo_sociales_propias(self, client):
        user, _ = self._login_with_notifications(client)
        response = client.get("/social/notificaciones/")
        assert response.status_code == 200
        titles = [n.title for n in response.context["page_obj"]]
        assert titles == ["like 1"]

    def test_marcar_leida_solo_propia(self, client):
        user, n1 = self._login_with_notifications(client)
        response = client.post(f"/social/notificaciones/{n1.pk}/leer/")
        assert response.status_code == 302
        n1.refresh_from_db()
        assert n1.read is True
        ajena = Notification.objects.get(title="ajeno")
        response = client.post(f"/social/notificaciones/{ajena.pk}/leer/")
        assert response.status_code == 404

    def test_marcar_todas(self, client):
        user, _ = self._login_with_notifications(client)
        client.post("/social/notificaciones/leer-todas/")
        assert not Notification.objects.filter(
            user=user, read=False, notification_type__startswith="SOCIAL_"
        ).exists()
        # La de gestión NO se toca
        assert Notification.objects.filter(user=user, read=False).count() == 1


@pytest.mark.django_db
class TestProfileViews:
    def test_perfil_platform_visible(self, client):
        owner = make_user("owner")
        Post.objects.create(author=owner, text="post público")
        viewer = make_user("viewer")
        client.force_login(viewer)
        response = client.get("/social/perfil/owner/")
        assert response.status_code == 200
        assert response.context["profile_user"] == owner

    def test_perfil_team_da_404_a_externos(self, client):
        owner = make_user("owner")
        profile = SocialProfileService.for_user(owner)
        profile.profile_visibility = SocialProfile.Visibility.TEAM
        profile.save()
        client.force_login(make_user("extraño"))
        assert client.get("/social/perfil/owner/").status_code == 404

    def test_perfil_inexistente_mismo_404(self, client):
        client.force_login(make_user("viewer"))
        assert client.get("/social/perfil/nadie/").status_code == 404

    def test_perfil_propio_redirect(self, client):
        user = make_user("bryan")
        client.force_login(user)
        response = client.get("/social/perfil/")
        assert response.status_code == 302
        assert response.url == "/social/perfil/bryan/"

    def test_hide_activity_oculta_comentarios_recientes(self, client):
        owner = make_user("owner")
        other = make_user("other")
        post = Post.objects.create(author=other, text="post de otro")
        FS.add_comment(owner, post, "comentario visible?")
        profile = SocialProfileService.for_user(owner)
        profile.hide_activity = True
        profile.save()
        client.force_login(make_user("viewer"))
        response = client.get("/social/perfil/owner/")
        assert response.context["recent_comments"] is None


@pytest.mark.django_db
class TestTeamPages:
    def _team_world(self):
        coach = make_user("coach")
        member = make_user("member")
        team = make_team(coach=coach, name="Galaxy")
        join(member, team)
        Post.objects.create(author=member, text="post del equipo")
        return team, member

    def test_directorio_lista_equipos_activos(self, client):
        team, _ = self._team_world()
        inactive = make_team(coach=make_user("c2"), name="Muerto")
        inactive.is_active = False
        inactive.save()
        client.force_login(make_user("viewer"))
        response = client.get("/social/equipos/")
        assert response.status_code == 200
        names = [t.name for t in response.context["page_obj"]]
        assert "Galaxy" in names and "Muerto" not in names

    def test_directorio_busqueda(self, client):
        self._team_world()
        make_team(coach=make_user("c3"), name="Cometas")
        client.force_login(make_user("viewer"))
        response = client.get("/social/equipos/?q=gala")
        names = [t.name for t in response.context["page_obj"]]
        assert names == ["Galaxy"]

    def test_pagina_equipo(self, client):
        team, member = self._team_world()
        client.force_login(make_user("viewer"))
        response = client.get(f"/social/equipo/{team.pk}/")
        assert response.status_code == 200
        assert response.context["team"] == team
        assert response.context["stats"]["num_athletes"] == 1
        posts = list(response.context["page_obj"])
        assert len(posts) == 1

    def test_pagina_equipo_respeta_privacidad(self, client):
        team, member = self._team_world()
        profile = SocialProfileService.for_user(member)
        profile.posts_visibility = SocialProfile.Visibility.TEAM
        profile.save()
        client.force_login(make_user("viewer"))
        response = client.get(f"/social/equipo/{team.pk}/")
        assert list(response.context["page_obj"]) == []

    def test_equipo_inactivo_404(self, client):
        team, _ = self._team_world()
        team.is_active = False
        team.save()
        client.force_login(make_user("viewer"))
        assert client.get(f"/social/equipo/{team.pk}/").status_code == 404


@pytest.mark.django_db
class TestSocialSettings:
    def test_get_renderiza_4_forms(self, client):
        client.force_login(make_user("bryan"))
        response = client.get("/social/configuracion/")
        assert response.status_code == 200
        for key in ("profile_form", "privacy_form", "notifications_form", "appearance_form"):
            assert key in response.context

    def test_post_privacidad(self, client):
        user = make_user("bryan")
        client.force_login(user)
        response = client.post(
            "/social/configuracion/",
            {
                "form_id": "privacy",
                "profile_visibility": "TEAM",
                "posts_visibility": "TEAM",
                "hide_activity": "on",
            },
        )
        assert response.status_code == 302  # PRG
        profile = SocialProfile.objects.get(user=user)
        assert profile.profile_visibility == "TEAM"
        assert profile.posts_visibility == "TEAM"
        assert profile.hide_activity is True

    def test_post_notificaciones(self, client):
        user = make_user("bryan")
        client.force_login(user)
        client.post("/social/configuracion/", {"form_id": "notifications"})  # todos off
        profile = SocialProfile.objects.get(user=user)
        assert not profile.notify_likes
        assert not profile.notify_comments
        assert not profile.notify_reposts

    def test_post_apariencia(self, client):
        user = make_user("bryan")
        client.force_login(user)
        client.post(
            "/social/configuracion/", {"form_id": "appearance", "feed_density": "COMPACT"}
        )
        assert SocialProfile.objects.get(user=user).feed_density == "COMPACT"

    def test_post_bio(self, client):
        user = make_user("bryan")
        client.force_login(user)
        client.post("/social/configuracion/", {"form_id": "profile", "bio": "Coach de Galaxy 🚀"})
        assert SocialProfile.objects.get(user=user).bio == "Coach de Galaxy 🚀"

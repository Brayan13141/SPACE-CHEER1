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

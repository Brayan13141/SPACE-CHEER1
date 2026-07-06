"""Notificaciones del portal social. Solo campana — sin email (spec)."""

from django.urls import reverse
from django.utils.translation import gettext as _

from accounts.models import Notification
from social.profile_services import SocialProfileService


class SocialNotificationService:
    @staticmethod
    def _create(recipient, actor, ntype, title, post_pk):
        """Regla central: nunca auto-notificar; respetar toggles del receptor;
        si el toggle está apagado NO se crea (no crear-y-ocultar)."""
        if recipient.pk == actor.pk or not recipient.is_active:
            return None
        prefs = SocialProfileService.for_user(recipient)
        enabled = {
            Notification.NotificationType.SOCIAL_LIKE: prefs.notify_likes,
            Notification.NotificationType.SOCIAL_COMMENT: prefs.notify_comments,
            Notification.NotificationType.SOCIAL_REPOST: prefs.notify_reposts,
        }[ntype]
        if not enabled:
            return None
        return Notification.objects.create(
            user=recipient,
            title=title,
            notification_type=ntype,
            url=reverse("social:post_detail", args=[post_pk]),
        )

    @staticmethod
    def _actor_name(actor):
        return actor.get_full_name() or actor.username

    @staticmethod
    def notify_like(actor, post):
        return SocialNotificationService._create(
            post.author,
            actor,
            Notification.NotificationType.SOCIAL_LIKE,
            _("A %(name)s le gustó tu publicación")
            % {"name": SocialNotificationService._actor_name(actor)},
            post.pk,
        )

    @staticmethod
    def notify_comment(actor, comment):
        return SocialNotificationService._create(
            comment.post.author,
            actor,
            Notification.NotificationType.SOCIAL_COMMENT,
            _("%(name)s comentó tu publicación")
            % {"name": SocialNotificationService._actor_name(actor)},
            comment.post_id,
        )

    @staticmethod
    def notify_repost(actor, repost):
        return SocialNotificationService._create(
            repost.shared_post.author,
            actor,
            Notification.NotificationType.SOCIAL_REPOST,
            _("%(name)s compartió tu publicación")
            % {"name": SocialNotificationService._actor_name(actor)},
            repost.shared_post_id,
        )

    @staticmethod
    def social_qs(user):
        return user.notifications.filter(notification_type__startswith="SOCIAL_")

    @staticmethod
    def unread_for(user, limit=10):
        return SocialNotificationService.social_qs(user).filter(read=False)[:limit]

    @staticmethod
    def mark_read(user, pk):
        from django.shortcuts import get_object_or_404

        notification = get_object_or_404(
            SocialNotificationService.social_qs(user), pk=pk
        )
        notification.read = True
        notification.save(update_fields=["read"])
        return notification

    @staticmethod
    def mark_all_read(user):
        return SocialNotificationService.social_qs(user).filter(read=False).update(
            read=True
        )

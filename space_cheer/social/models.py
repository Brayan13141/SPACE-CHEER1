from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.file_utils import validate_image_magic

MAX_IMAGE_MB = 5


def validate_image_max_5mb(file):
    """Rechaza imágenes de más de 5 MB (límite del feed social)."""
    if file.size > MAX_IMAGE_MB * 1024 * 1024:
        raise ValidationError(
            _("La imagen no puede pesar más de %(mb)s MB.") % {"mb": MAX_IMAGE_MB}
        )


class PostQuerySet(models.QuerySet):
    def visible_for_viewer(self, viewer):
        """Punto único de verdad de visibilidad de posts.

        Reglas (spec 2026-07-05-social-portal):
        - Autores inactivos: fuera para todos (incluido ADMIN).
        - ADMIN/superuser: bypass de privacidad.
        - Sin SocialProfile o PLATFORM: visible para toda la plataforma.
        - TEAM: visible solo si autor y viewer comparten equipo con
          membresía activa (evaluado en vivo, cada request).
        - El autor siempre ve lo propio.
        """
        from teams.models import UserTeamMembership

        qs = self.filter(author__is_active=True)
        if viewer.is_superuser or viewer.roles.filter(name="ADMIN").exists():
            return qs
        viewer_team_ids = UserTeamMembership.objects.filter(
            user=viewer, is_active=True
        ).values("team_id")
        teammate_ids = UserTeamMembership.objects.filter(
            team_id__in=viewer_team_ids, is_active=True
        ).values("user_id")
        return qs.filter(
            models.Q(author=viewer)
            | models.Q(author__social_profile__isnull=True)
            | models.Q(author__social_profile__posts_visibility="PLATFORM")
            | models.Q(
                author__social_profile__posts_visibility="TEAM",
                author_id__in=teammate_ids,
            )
        )


class Post(models.Model):
    """Publicación del feed. Si shared_post no es nulo, es un repost."""

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="social_posts",
    )
    text = models.TextField(max_length=2000, blank=True)
    # CASCADE: si se borra el original, sus reposts desaparecen con él
    # (un repost sin original sería indistinguible de un post normal).
    shared_post = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="reposts",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = PostQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["-created_at"])]

    def __str__(self):
        return f"Post #{self.pk} de {self.author.username}"


class PostImage(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(
        upload_to="social/posts/%Y/%m/",
        validators=[validate_image_magic, validate_image_max_5mb],
    )
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return f"Imagen {self.order} de post #{self.post_id}"


class PostLike(models.Model):
    class Reaction(models.TextChoices):
        APPLAUSE = "APPLAUSE", _("Aplausos")
        FIRE = "FIRE", _("Fuego")
        STAR = "STAR", _("Increíble")
        HEART = "HEART", _("Me encanta")
        MUSCLE = "MUSCLE", _("Ánimo")

    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="likes")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="post_likes",
    )
    reaction = models.CharField(
        max_length=10, choices=Reaction.choices, default=Reaction.APPLAUSE
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["post", "user"], name="unique_post_like")
        ]

    def __str__(self):
        return f"Reacción {self.reaction} de {self.user.username} a post #{self.post_id}"


class PostComment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="post_comments",
    )
    text = models.TextField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Comentario de {self.author.username} en post #{self.post_id}"


class SocialProfile(models.Model):
    """Perfil del portal social: identidad, privacidad, preferencias y apariencia.

    Separado del perfil operativo de accounts: estos campos solo aplican
    dentro del espacio social. NO confundir con accounts.PrivacySettings
    (perfil operativo) ni accounts.NotificationPreferences (canal email).
    """

    class Visibility(models.TextChoices):
        PLATFORM = "PLATFORM", _("Toda la plataforma")
        TEAM = "TEAM", _("Solo mi equipo")

    class FeedDensity(models.TextChoices):
        COMFORTABLE = "COMFORTABLE", _("Cómoda")
        COMPACT = "COMPACT", _("Compacta")

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="social_profile",
    )
    bio = models.TextField(max_length=300, blank=True)
    avatar = models.ImageField(
        upload_to="social/profiles/avatars/%Y/%m/",
        blank=True,
        validators=[validate_image_magic, validate_image_max_5mb],
    )
    cover = models.ImageField(
        upload_to="social/profiles/covers/%Y/%m/",
        blank=True,
        validators=[validate_image_magic, validate_image_max_5mb],
    )
    profile_visibility = models.CharField(
        max_length=10, choices=Visibility.choices, default=Visibility.PLATFORM
    )
    posts_visibility = models.CharField(
        max_length=10, choices=Visibility.choices, default=Visibility.PLATFORM
    )
    hide_activity = models.BooleanField(default=False)
    feed_density = models.CharField(
        max_length=12, choices=FeedDensity.choices, default=FeedDensity.COMFORTABLE
    )
    notify_likes = models.BooleanField(default=True)
    notify_comments = models.BooleanField(default=True)
    notify_reposts = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"SocialProfile de {self.user.username}"

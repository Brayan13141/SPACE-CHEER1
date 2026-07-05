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
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="likes")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="post_likes",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["post", "user"], name="unique_post_like")
        ]

    def __str__(self):
        return f"Like de {self.user.username} a post #{self.post_id}"


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

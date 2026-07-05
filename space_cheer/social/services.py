"""Service layer del feed social. Toda la lógica de negocio vive aquí,
siguiendo el patrón del proyecto (vistas delgadas)."""

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Count, Exists, OuterRef, Prefetch
from django.utils.translation import gettext_lazy as _

from social.models import Post, PostComment, PostImage, PostLike


class FeedService:
    MAX_IMAGES = 4

    # ── Helpers ──────────────────────────────────────────────────────────
    @staticmethod
    def is_admin(user):
        return user.is_superuser or user.roles.filter(name="ADMIN").exists()

    @staticmethod
    def _can_moderate(user, author_id):
        return user.pk == author_id or FeedService.is_admin(user)

    # ── Lectura ──────────────────────────────────────────────────────────
    @staticmethod
    def feed_queryset(user):
        """Feed completo optimizado: autor, repost embebido, imágenes,
        contadores y 'yo di like', sin N+1."""
        recent_comments = Prefetch(
            "comments",
            queryset=PostComment.objects.select_related("author").order_by(
                "-created_at", "-id"
            ),
            to_attr="recent_comments",
        )
        return (
            Post.objects.select_related("author", "shared_post", "shared_post__author")
            .prefetch_related("images", "shared_post__images", recent_comments)
            .annotate(
                like_count=Count("likes", distinct=True),
                comment_count=Count("comments", distinct=True),
                liked_by_me=Exists(
                    PostLike.objects.filter(post=OuterRef("pk"), user=user)
                ),
            )
            .order_by("-created_at", "-id")
        )

    # ── Escritura ────────────────────────────────────────────────────────
    @staticmethod
    @transaction.atomic
    def create_post(user, text, images=None):
        images = images or []
        text = (text or "").strip()
        if not text and not images:
            raise ValidationError(_("La publicación necesita texto o al menos una imagen."))
        if len(images) > FeedService.MAX_IMAGES:
            raise ValidationError(
                _("Máximo %(n)s imágenes por publicación.") % {"n": FeedService.MAX_IMAGES}
            )
        post = Post.objects.create(author=user, text=text)
        post_images = [
            PostImage(post=post, image=img, order=i) for i, img in enumerate(images)
        ]
        for post_image in post_images:
            post_image.full_clean()  # valida TODAS antes de escribir archivos
        for post_image in post_images:
            post_image.save()
        return post

    @staticmethod
    def create_repost(user, original, text=""):
        # Compartir un repost comparte el post original (como Facebook)
        if original.shared_post_id:
            original = original.shared_post
        return Post.objects.create(
            author=user, text=(text or "").strip(), shared_post=original
        )

    @staticmethod
    def toggle_like(user, post):
        like, created = PostLike.objects.get_or_create(post=post, user=user)
        if not created:
            like.delete()
        return created, post.likes.count()

    @staticmethod
    def add_comment(user, post, text):
        text = (text or "").strip()
        if not text:
            raise ValidationError(_("El comentario no puede estar vacío."))
        return PostComment.objects.create(post=post, author=user, text=text)

    @staticmethod
    @transaction.atomic
    def delete_post(user, post):
        if not FeedService._can_moderate(user, post.author_id):
            raise PermissionDenied
        # Borrar archivos físicos antes del CASCADE (incluye los de reposts propios: no tienen imágenes)
        for img in post.images.all():
            img.image.delete(save=False)
        post.delete()

    @staticmethod
    def delete_comment(user, comment):
        allowed = FeedService._can_moderate(
            user, comment.author_id
        ) or user.pk == comment.post.author_id
        if not allowed:
            raise PermissionDenied
        comment.delete()


class RankingService:
    """Ranking de equipos con métricas calculadas en vivo (sin modelos nuevos)."""

    SORT_FIELDS = {
        "competitions": "-num_competitions",
        "athletes": "-num_athletes",
        "posts": "-num_posts",
    }

    @staticmethod
    def team_ranking(sort_key="competitions"):
        from django.db.models import Q
        from teams.models import Team

        order = RankingService.SORT_FIELDS.get(sort_key, "-num_competitions")
        return (
            Team.objects.filter(is_active=True)
            .annotate(
                num_competitions=Count(
                    "event_registrations",
                    filter=Q(event_registrations__status="ACCEPTED"),
                    distinct=True,
                ),
                num_athletes=Count(
                    "memberships",
                    filter=Q(memberships__is_active=True),
                    distinct=True,
                ),
                num_posts=Count(
                    "memberships__user__social_posts",
                    filter=Q(memberships__is_active=True),
                    distinct=True,
                ),
            )
            .order_by(order, "name")
        )

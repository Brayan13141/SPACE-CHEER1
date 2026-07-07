"""Service layer del feed social. Toda la lógica de negocio vive aquí,
siguiendo el patrón del proyecto (vistas delgadas)."""

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Count, Exists, OuterRef, Prefetch, Subquery
from django.utils.translation import gettext_lazy as _

from social.models import Post, PostComment, PostImage, PostLike
from social.notification_services import SocialNotificationService


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
            queryset=PostComment.objects.select_related(
                "author", "author__social_profile"
            ).order_by("-created_at", "-id"),
            to_attr="recent_comments",
        )
        return (
            Post.objects.visible_for_viewer(user)
            .select_related(
                "author",
                "author__social_profile",
                "shared_post",
                "shared_post__author",
                "shared_post__author__social_profile",
            )
            .prefetch_related(
                "images",
                "shared_post__images",
                "author__roles",
                "shared_post__author__roles",
                recent_comments,
            )
            .annotate(
                like_count=Count("likes", distinct=True),
                comment_count=Count("comments", distinct=True),
                liked_by_me=Exists(
                    PostLike.objects.filter(post=OuterRef("pk"), user=user)
                ),
                my_reaction=Subquery(
                    PostLike.objects.filter(post=OuterRef("pk"), user=user).values(
                        "reaction"
                    )[:1]
                ),
                shared_visible=Exists(
                    Post.objects.visible_for_viewer(user).filter(
                        pk=OuterRef("shared_post_id")
                    )
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
        repost = Post.objects.create(
            author=user, text=(text or "").strip(), shared_post=original
        )
        SocialNotificationService.notify_repost(user, repost)
        return repost

    @staticmethod
    def toggle_like(user, post, reaction=PostLike.Reaction.APPLAUSE):
        """Reacción estilo Facebook: click en tu misma reacción la quita;
        click en una distinta la cambia; sin reacción previa, la crea."""
        like, created = PostLike.objects.get_or_create(
            post=post, user=user, defaults={"reaction": reaction}
        )
        if created:
            SocialNotificationService.notify_like(user, post)
        elif like.reaction == reaction:
            like.delete()
            created = False
        else:
            like.reaction = reaction
            like.save(update_fields=["reaction"])
            created = True
        return created, post.likes.count()

    @staticmethod
    def add_comment(user, post, text):
        text = (text or "").strip()
        if not text:
            raise ValidationError(_("El comentario no puede estar vacío."))
        comment = PostComment.objects.create(post=post, author=user, text=text)
        SocialNotificationService.notify_comment(user, comment)
        return comment

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


class PeopleDiscoveryService:
    """Fuentes de datos reales para la barra de historias y sugerencias del
    feed. Sin sistema de amistad/follow todavía (subsistema futuro) — solo
    lectura de compañeros de equipo activos."""

    @staticmethod
    def _teammate_ids(user):
        from teams.models import UserTeamMembership

        my_team_ids = UserTeamMembership.objects.filter(
            user=user, is_active=True
        ).values("team_id")
        return (
            UserTeamMembership.objects.filter(team_id__in=my_team_ids, is_active=True)
            .exclude(user_id=user.pk)
            .values_list("user_id", flat=True)
            .distinct()
        )

    @staticmethod
    def recent_active_teammates(user, limit=8):
        """Para la barra de accesos rápidos: compañeros con publicaciones
        recientes. No son 'historias' efímeras, son acceso directo a perfil."""
        from django.contrib.auth import get_user_model

        User = get_user_model()
        return (
            User.objects.filter(pk__in=PeopleDiscoveryService._teammate_ids(user))
            .filter(social_posts__isnull=False)
            .select_related("social_profile")
            .distinct()
            .order_by("-social_posts__created_at")[:limit]
        )

    @staticmethod
    def suggested_teammates(user, limit=3):
        """Compañeros de equipo que el usuario probablemente ya conoce.
        Sin botón de 'Seguir' funcional todavía — enlaza a su perfil."""
        from django.contrib.auth import get_user_model

        User = get_user_model()
        return (
            User.objects.filter(pk__in=PeopleDiscoveryService._teammate_ids(user))
            .select_related("social_profile")
            .order_by("?")[:limit]
        )


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

    @staticmethod
    def team_stats(team):
        """Métricas + posición de un equipo en el ranking por competencias."""
        ranking = list(RankingService.team_ranking("competitions"))
        position = None
        stats = {"num_competitions": 0, "num_athletes": 0, "num_posts": 0}
        for i, t in enumerate(ranking, start=1):
            if t.pk == team.pk:
                position = i
                stats = {
                    "num_competitions": t.num_competitions,
                    "num_athletes": t.num_athletes,
                    "num_posts": t.num_posts,
                }
                break
        stats["rank_position"] = position
        stats["total_teams"] = len(ranking)
        return stats

    @staticmethod
    def upcoming_tournament_for_user(user):
        """Próximo torneo donde compite al menos un equipo del usuario,
        con cuántos equipos de su red (ranking) también están inscritos."""
        from django.utils import timezone
        from events.models import Event, EventTeamRegistration
        from teams.models import UserTeamMembership

        my_team_ids = list(
            UserTeamMembership.objects.filter(
                user=user, is_active=True
            ).values_list("team_id", flat=True)
        )
        if not my_team_ids:
            return None
        event = (
            Event.objects.filter(
                start_date__gte=timezone.localdate(),
                team_registrations__team_id__in=my_team_ids,
                team_registrations__status=EventTeamRegistration.STATUS_ACCEPTED,
            )
            .order_by("start_date")
            .distinct()
            .first()
        )
        if not event:
            return None
        days_left = (event.start_date - timezone.localdate()).days
        teams_competing = EventTeamRegistration.objects.filter(
            event=event, status=EventTeamRegistration.STATUS_ACCEPTED
        ).count()
        return {
            "event": event,
            "days_left": days_left,
            "teams_competing": teams_competing,
        }

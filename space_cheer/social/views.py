from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.paginator import Paginator
from django.http import Http404, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST
from invitations.utils import get_invitation_model
from django_ratelimit.decorators import ratelimit

from accounts.decorators import role_required
from social.models import Post, PostComment, PostLike
from social.notification_services import SocialNotificationService
from social.profile_services import SocialProfileService, SocialVisibilityService
from social.services import FeedService, RankingService

Invitation = get_invitation_model()


@role_required("HEADCOACH", "COACH", "ADMIN")
@ratelimit(key="user", rate="10/h", method="POST", block=True)
def send_invite(request):
    if request.method == "POST":
        email = request.POST.get("email", "").strip()

        if not email:
            messages.error(request, "Por favor ingresa un email válido.")
            return redirect("social:send_invite")

        try:
            validate_email(email)
        except ValidationError:
            messages.error(request, "El email no tiene un formato válido.")
            return redirect("social:send_invite")

        existing = Invitation.objects.filter(email=email, accepted=False).first()

        if existing:
            if existing.sent is None or existing.key_expired():
                existing.delete()
            else:
                messages.warning(
                    request, f"Ya hay una invitación pendiente para {email}."
                )
                return redirect("social:send_invite")

        invite = Invitation.create(email=email, inviter=request.user)
        invite.sent = timezone.now()
        invite.save()
        invite.send_invitation(request)

        messages.success(request, f"Invitación enviada a {email}")
        return redirect("social:send_invite")

    return render(request, "social/send_invite.html")


def _safe_next(request, fallback="social:feed"):
    """Redirige a ?next= solo si es una URL local (guard anti open-redirect)."""
    nxt = request.POST.get("next") or request.GET.get("next")
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
        return redirect(nxt)
    return redirect(fallback)


@login_required
def feed(request):
    paginator = Paginator(FeedService.feed_queryset(request.user), 10)
    page_obj = paginator.get_page(request.GET.get("page"))
    profile = SocialProfileService.for_user(request.user)
    return render(
        request,
        "social/feed.html",
        {
            "page_obj": page_obj,
            "feed_is_admin": FeedService.is_admin(request.user),
            "social_feed_density": profile.feed_density,
        },
    )


@login_required
@ratelimit(key="user", rate="30/h", method="POST", block=True)
@require_POST
def post_create(request):
    try:
        FeedService.create_post(
            request.user,
            text=request.POST.get("text", ""),
            images=request.FILES.getlist("images"),
        )
        messages.success(request, _("Publicación creada."))
    except DjangoValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    return redirect("social:feed")


@login_required
def post_detail(request, pk):
    post = get_object_or_404(FeedService.feed_queryset(request.user), pk=pk)
    return render(
        request,
        "social/post_detail.html",
        {"post": post, "feed_is_admin": FeedService.is_admin(request.user)},
    )


@login_required
@require_POST
def post_like_toggle(request, pk):
    post = get_object_or_404(Post, pk=pk)
    liked, like_count = FeedService.toggle_like(request.user, post)
    return JsonResponse({"liked": liked, "like_count": like_count})


@login_required
@ratelimit(key="user", rate="30/h", method="POST", block=True)
@require_POST
def comment_create(request, pk):
    post = get_object_or_404(Post, pk=pk)
    try:
        FeedService.add_comment(request.user, post, request.POST.get("text", ""))
    except DjangoValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    return _safe_next(request)


@login_required
@ratelimit(key="user", rate="30/h", method="POST", block=True)
@require_POST
def repost_create(request, pk):
    original = get_object_or_404(Post, pk=pk)
    FeedService.create_repost(request.user, original, request.POST.get("text", ""))
    messages.success(request, _("Publicación compartida."))
    return redirect("social:feed")


@login_required
@require_POST
def post_delete(request, pk):
    post = get_object_or_404(Post, pk=pk)
    FeedService.delete_post(request.user, post)  # PermissionDenied → 403
    messages.success(request, _("Publicación eliminada."))
    return redirect("social:feed")


@login_required
@require_POST
def comment_delete(request, pk):
    comment = get_object_or_404(PostComment.objects.select_related("post"), pk=pk)
    FeedService.delete_comment(request.user, comment)
    return _safe_next(request)


@login_required
def team_ranking(request):
    sort = request.GET.get("sort", "competitions")
    if sort not in RankingService.SORT_FIELDS:
        sort = "competitions"
    return render(
        request,
        "social/ranking.html",
        {"teams": RankingService.team_ranking(sort), "sort": sort},
    )


@login_required
def profile_me(request):
    return redirect("social:profile_detail", username=request.user.username)


@login_required
def profile_detail(request, username):
    User = get_user_model()
    try:
        profile_user = User.objects.get(username=username, is_active=True)
    except User.DoesNotExist:
        raise Http404
    if not SocialVisibilityService.can_view_profile(request.user, profile_user):
        raise Http404  # mismo 404 que inexistente: no filtrar perfiles privados
    profile = SocialProfileService.for_user(profile_user)
    posts = FeedService.feed_queryset(request.user).filter(author=profile_user)
    paginator = Paginator(posts, 10)
    page_obj = paginator.get_page(request.GET.get("page"))
    stats = {
        "posts": Post.objects.filter(author=profile_user).count(),
        "likes_received": PostLike.objects.filter(post__author=profile_user).count(),
        "teams": profile_user.team_memberships.filter(is_active=True).count(),
    }
    recent_comments = None
    if not profile.hide_activity:
        recent_comments = (
            PostComment.objects.filter(author=profile_user)
            .filter(post__in=Post.objects.visible_for_viewer(request.user))
            .select_related("post")
            .order_by("-created_at")[:5]
        )
    return render(
        request,
        "social/profile.html",
        {
            "profile_user": profile_user,
            "profile": profile,
            "page_obj": page_obj,
            "stats": stats,
            "recent_comments": recent_comments,
            "feed_is_admin": FeedService.is_admin(request.user),
        },
    )


@login_required
def team_directory(request):
    from teams.models import Team

    teams = Team.objects.filter(is_active=True).order_by("name")
    query = request.GET.get("q", "").strip()
    if query:
        teams = teams.filter(name__icontains=query)
    paginator = Paginator(teams, 12)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(
        request, "social/team_directory.html", {"page_obj": page_obj, "q": query}
    )


@login_required
def team_page(request, pk):
    from teams.models import Team

    team = get_object_or_404(Team, pk=pk, is_active=True)
    members = (
        team.memberships.filter(is_active=True)
        .select_related("user")
        .order_by("user__username")
    )
    member_ids = [m.user_id for m in members]
    posts = FeedService.feed_queryset(request.user).filter(author_id__in=member_ids)
    paginator = Paginator(posts, 10)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "social/team_page.html",
        {
            "team": team,
            "members": members,
            "page_obj": page_obj,
            "stats": RankingService.team_stats(team),
            "feed_is_admin": FeedService.is_admin(request.user),
        },
    )


@login_required
def notifications(request):
    qs = SocialNotificationService.social_qs(request.user)
    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "social/notifications.html", {"page_obj": page_obj})


@login_required
@require_POST
def notification_read(request, pk):
    notification = SocialNotificationService.mark_read(request.user, pk)
    if notification.url:
        return redirect(notification.url)
    return redirect("social:notifications")


@login_required
@require_POST
def notifications_read_all(request):
    SocialNotificationService.mark_all_read(request.user)
    return _safe_next(request, fallback="social:notifications")


@login_required
def social_settings(request):
    from django.http import Http404
    raise Http404  # Task 9

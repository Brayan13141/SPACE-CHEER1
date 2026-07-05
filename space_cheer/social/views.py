from django.contrib.auth.decorators import login_required
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST
from invitations.utils import get_invitation_model
from django_ratelimit.decorators import ratelimit

from accounts.decorators import role_required
from social.models import Post, PostComment
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
    return render(
        request,
        "social/feed.html",
        {"page_obj": page_obj, "feed_is_admin": FeedService.is_admin(request.user)},
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

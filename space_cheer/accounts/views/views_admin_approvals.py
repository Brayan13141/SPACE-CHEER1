from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from accounts.decorators import role_required
from accounts.models import CoachProfile
from accounts.services.coach_approval_service import CoachApprovalService


@role_required("ADMIN")
@require_http_methods(["GET", "POST"])
def headcoach_approvals(request):
    if request.method == "POST":
        action = request.POST.get("action")
        profile = get_object_or_404(CoachProfile, pk=request.POST.get("profile_id"))
        if action == "approve":
            CoachApprovalService.approve_headcoach(profile, by=request.user)
            messages.success(request, f"{profile.user} aprobado y activado.")
        elif action == "reject":
            reason = request.POST.get("reason", "").strip()
            CoachApprovalService.reject_headcoach(profile, by=request.user, reason=reason)
            messages.info(request, f"{profile.user} rechazado.")
        return redirect("accounts:headcoach_approvals")

    pending_profiles = (
        CoachProfile.objects.filter(
            approval_status=CoachProfile.PENDING,
            user__roles__name="HEADCOACH",
        )
        .select_related("user")
        .distinct()
    )
    pending = [p.user for p in pending_profiles]
    return render(
        request,
        "account/admin/headcoach_approvals.html",
        {"pending_profiles": pending_profiles, "pending": pending},
    )

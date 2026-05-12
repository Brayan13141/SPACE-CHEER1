from django.urls import reverse


def get_user_redirect_flow(user):
    if not user.is_authenticated:
        return reverse("account_login")

    if not user.roles.exists():
        return reverse("accounts:profile_setup")

    role = user.roles.first()

    if not user.profile_completed:
        return reverse("accounts:profile_setup")

    if role.requires_curp and not user.curp:
        return reverse("accounts:curp_verification")

    # Coach/Headcoach pendiente de aprobación o rechazado
    if user.roles.filter(name__in=["COACH", "HEADCOACH"]).exists():
        try:
            status = user.coachprofile.approval_status
            if status == "PENDING":
                return reverse("accounts:coach_pending_approval")
            if status == "REJECTED":
                return reverse("accounts:coach_rejected")
        except Exception:
            pass

    # Menor sin guardian → pantalla de bloqueo
    if user.roles.filter(name="ATHLETE").exists() and user.is_minor:
        from custody.services.minor_access_service import MinorAccessService
        if MinorAccessService.get_access_level(user) == MinorAccessService.BLOCKED:
            return reverse("guardian:minor_blocked")

    if user.roles.filter(name="ADMIN").exists():
        return reverse("core:dashboard")

    if user.roles.filter(name="HEADCOACH").exists():
        return reverse("core:dashboard")

    if user.roles.filter(name="GUARDIAN").exists():
        return reverse("guardian:dashboard")

    if user.roles.filter(name="ATHLETE").exists():
        return reverse("core:dashboard")

    return reverse("core:dashboard")

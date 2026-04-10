# accounts/utils/redirect_flow.py
# Este módulo centraliza la lógica de redirección de usuarios según su estado.
# Así evitamos tener lógica de redirección dispersa por toda la app.

from django.urls import reverse


def get_user_redirect_flow(user):
    """
    Decide EXACTAMENTE a dónde debe ir el usuario
    según su estado completo.

    Prioridad:
    1. Autenticación
    2. Perfil / onboarding
    3. CURP
    4. Dashboard por rol
    """
    if not user.is_authenticated:
        return reverse("account_login")

    # 1. Sin rol → onboarding
    if not user.roles.exists():
        return reverse("accounts:profile_setup")

    role = user.roles.first()

    if not user.profile_completed:
        return reverse("accounts:profile_setup")

    # 2. CURP requerido
    if role.requires_curp and not user.curp:
        return reverse("accounts:curp_verification")

    # 3. Redirección por rol
    if user.roles.filter(name="ADMIN").exists():
        return reverse("core:dashboard")

    if user.roles.filter(name="HEADCOACH").exists():
        return reverse("core:dashboard")

    if user.roles.filter(name="GUARDIAN").exists():
        return reverse("guardian:dashboard")

    if user.roles.filter(name="ATHLETE").exists():
        return reverse("core:dashboard")

    return reverse("core:dashboard")

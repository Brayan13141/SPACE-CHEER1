# accounts/mixins.py
"""
Mixins para Class-Based Views (CBV).

Equivalentes de los decoradores FBV pero para CBV.
Usar con LoginView, DetailView, ListView, etc.

Uso:
    from accounts.mixins import FullProfileRequiredMixin, RoleRequiredMixin

    class MiVista(FullProfileRequiredMixin, RoleRequiredMixin, ListView):
        allowed_roles = ["HEADCOACH", "ADMIN"]
        model = Team

    # O con method_decorator en CBV existentes:
    from django.utils.decorators import method_decorator
    from accounts.decorators import full_profile_required, role_required

    @method_decorator(full_profile_required, name="dispatch")
    @method_decorator(role_required("ADMIN"), name="dispatch")
    class AdminView(TemplateView): ...

Nota sobre orden de herencia:
    Los mixins SIEMPRE van antes que la view base en la lista de herencia.
    ✓ class MiVista(FullProfileRequiredMixin, RoleRequiredMixin, ListView)
    ✗ class MiVista(ListView, FullProfileRequiredMixin, RoleRequiredMixin)
"""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# MIXIN: Perfil completo requerido
# =============================================================================


class FullProfileRequiredMixin(LoginRequiredMixin):
    """
    Equivalente CBV de @full_profile_required.

    Cadena de redirección:
    1. No autenticado → login (LoginRequiredMixin)
    2. Sin rol → profile_setup
    3. Rol requiere CURP y no tiene → curp_verification
    4. Superuser → siempre pasa

    Uso:
        class MiVista(FullProfileRequiredMixin, TemplateView):
            template_name = "..."
    """

    def dispatch(self, request, *args, **kwargs):
        # LoginRequiredMixin maneja el check de autenticación
        response = super().dispatch(request, *args, **kwargs)
        if not request.user.is_authenticated:
            return response

        user = request.user

        # Superuser pasa siempre
        if user.is_superuser:
            return response

        # Sin rol → setup de perfil
        if not user.roles.exists():
            return redirect("accounts:profile_setup")

        # Rol requiere CURP y no tiene
        role = user.roles.first()
        if role and role.requires_curp and not user.curp:
            return redirect("accounts:curp_verification")

        return response


# =============================================================================
# MIXIN: Rol requerido
# =============================================================================


class RoleRequiredMixin(FullProfileRequiredMixin):
    """
    Equivalente CBV de @role_required(*roles).

    Atributo requerido en la subclase:
        allowed_roles = ["ADMIN", "HEADCOACH"]

    Hereda de FullProfileRequiredMixin: siempre verifica perfil antes de rol.

    Uso:
        class AdminView(RoleRequiredMixin, TemplateView):
            allowed_roles = ["ADMIN"]
            template_name = "admin/dashboard.html"
    """

    # Subclases deben definir esto
    allowed_roles: list = []

    def dispatch(self, request, *args, **kwargs):
        # Verificar perfil (herencia de FullProfileRequiredMixin)
        response = super().dispatch(request, *args, **kwargs)

        if not request.user.is_authenticated:
            return response

        user = request.user

        # Superuser pasa siempre
        if user.is_superuser:
            return response

        # Verificar rol
        if not self.allowed_roles:
            logger.warning(
                "%s no define allowed_roles — denegando por defecto",
                self.__class__.__name__,
            )
            raise PermissionDenied

        user_roles = set(user.roles.values_list("name", flat=True))

        if user_roles.intersection(set(self.allowed_roles)):
            return response

        messages.error(request, "No tienes permisos para acceder a esta sección.")
        logger.warning(
            "Acceso denegado: %s (roles: %s) intentó acceder a %s (requiere: %s)",
            user.username,
            user_roles,
            self.__class__.__name__,
            self.allowed_roles,
        )
        return redirect("dashboard")


# =============================================================================
# MIXIN: Ownership requerido
# =============================================================================


class OwnsAthleteMixin:
    """
    Verifica que el coach autenticado posee al atleta especificado en la URL.
    Requiere parámetro `athlete_id` o `user_id` en la URL.

    Admin y superuser siempre pasan.

    Uso:
        class EditAthleteMeasuresView(FullProfileRequiredMixin, OwnsAthleteMixin, UpdateView):
            athlete_url_kwarg = "athlete_id"  # nombre del parámetro en URL
    """

    # Nombre del parámetro en la URL (default: "athlete_id")
    athlete_url_kwarg = "athlete_id"

    def dispatch(self, request, *args, **kwargs):
        from accounts.models import UserOwnership

        user = request.user

        # Admin y superuser pasan siempre
        if user.is_superuser or user.roles.filter(name="ADMIN").exists():
            return super().dispatch(request, *args, **kwargs)

        # Obtener ID del atleta de los kwargs de URL
        athlete_id = kwargs.get(self.athlete_url_kwarg) or kwargs.get("user_id")

        if athlete_id:
            owns = UserOwnership.objects.filter(
                owner=user,
                user_id=athlete_id,
                is_active=True,
            ).exists()

            if not owns:
                messages.error(request, "No tienes acceso a este atleta.")
                return redirect("manage_owned_users")

        return super().dispatch(request, *args, **kwargs)


# =============================================================================
# MIXIN: Datos PII — loggea acceso automáticamente
# =============================================================================


class PiiAccessMixin:
    """
    Loggea automáticamente el acceso a la view como acceso a datos PII.

    Atributos a definir en la subclase:
        pii_access_type = "VIEW_MEDICAL"     # requerido
        pii_target_kwarg = "athlete_id"      # nombre del kwarg con el ID del target
        pii_field_accessed = "medical_info"  # campo accedido (opcional)

    Uso:
        class MedicalInfoView(FullProfileRequiredMixin, PiiAccessMixin, DetailView):
            pii_access_type = "VIEW_MEDICAL"
            pii_target_kwarg = "pk"
    """

    pii_access_type: str = ""
    pii_target_kwarg: str = "pk"
    pii_field_accessed: str = ""

    def dispatch(self, request, *args, **kwargs):
        from accounts.services.pii_audit_service import PiiAuditService
        from django.contrib.auth import get_user_model

        response = super().dispatch(request, *args, **kwargs)

        # Solo loggear respuestas exitosas (200)
        if (
            self.pii_access_type
            and request.user.is_authenticated
            and hasattr(response, "status_code")
            and response.status_code == 200
        ):
            target_id = kwargs.get(self.pii_target_kwarg)
            target_user = None

            if target_id:
                UserModel = get_user_model()
                target_user = UserModel.objects.filter(id=target_id).first()

            PiiAuditService.log(
                request=request,
                target_user=target_user,
                access_type=self.pii_access_type,
                field_accessed=self.pii_field_accessed,
            )

        return response

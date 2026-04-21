# accounts/services/permission_service.py
"""
Matriz de permisos centralizada — Principio de Mínimo Privilegio (PoLP).

¿Por qué este archivo existe?
Antes de este servicio, la lógica de "¿puede X hacer Y?" estaba dispersa en:
- coach/views.py
- orders/permissions.py
- accounts/decorators.py
- custody/services/minor_service.py

Eso es un problema de mantenimiento: cambiar una regla requiere buscar en 4 archivos.
Ahora hay una sola fuente de verdad.

MATRIZ DE PERMISOS:
┌──────────────────────────┬───────┬────────────┬───────┬───────┬────────┬──────────┐
│ Acción                   │ ADMIN │ HEADCOACH  │ COACH │ STAFF │ ATLETA │ GUARDIAN │
├──────────────────────────┼───────┼────────────┼───────┼───────┼────────┼──────────┤
│ Ver perfil propio        │  ✓    │     ✓      │   ✓   │   ✓   │   ✓    │    ✓     │
│ Editar perfil propio     │  ✓    │     ✓      │   ✓   │   ✓   │   ✓    │    ✓     │
│ Ver datos de atleta      │  ✓    │  Solo suyos│  Own  │   ✗   │ Propio │ Sus hijos│
│ Ver medidas de atleta    │  ✓    │  Solo suyos│  Own  │   ✗   │ Propio │ Sus hijos│
│ Ver CURP                 │  ✓    │     ✓      │   ✗   │   ✗   │ Propio │    ✗     │
│ Ver datos médicos        │  ✓    │  Solo suyos│   ✗   │   ✗   │ Propio │ Sus hijos│
│ Crear atletas            │  ✓    │     ✓      │   ✗   │   ✗   │   ✗    │    ✗     │
│ Importar CSV             │  ✓    │     ✓      │   ✗   │   ✗   │   ✗    │    ✗     │
│ Gestionar equipos        │  ✓    │  Sus equipos│  ✗   │   ✗   │   ✗    │    ✗     │
│ Ver órdenes              │  ✓    │  Sus equipos│  ✗   │   ✓   │ Propias│ Hijos    │
│ Crear órdenes            │  ✓    │     ✓      │   ✗   │   ✗   │   ✓    │ p/hijos  │
│ Inscribir a eventos      │  ✓    │     ✓      │   ✓   │   ✗   │   ✓    │ p/hijos  │
└──────────────────────────┴───────┴────────────┴───────┴───────┴────────┴──────────┘
"""

import logging
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)
User = get_user_model()


class AccountPermissions:
    """
    Punto único de verificación de permisos para el módulo accounts.

    Uso desde cualquier view o service:
        if not AccountPermissions.can_view_athlete_data(request.user, athlete):
            raise PermissionDenied
    """

    # =========================================================================
    # PERMISOS DE PERFIL
    # =========================================================================

    @staticmethod
    def can_edit_own_profile(user) -> bool:
        """Cualquier usuario autenticado puede editar su propio perfil."""
        return user.is_authenticated

    @staticmethod
    def can_view_profile(viewer, target_user) -> bool:
        """
        ¿Puede `viewer` ver el perfil de `target_user`?
        Considera PrivacySettings del target.
        """
        if viewer == target_user:
            return True

        if AccountPermissions._is_admin(viewer):
            return True

        # Verificar privacy settings del target
        try:
            privacy = target_user.privacy_settings
            if privacy.profile_visibility == "PUBLIC":
                return True
            if privacy.profile_visibility == "TEAM":
                return AccountPermissions._share_team(viewer, target_user)
            # PRIVATE: solo admin o el propio usuario (ya cubiertos)
            return False
        except Exception:
            # Sin privacy settings → usar default TEAM
            return AccountPermissions._share_team(viewer, target_user)

    # =========================================================================
    # PERMISOS DE DATOS SENSIBLES
    # =========================================================================

    @staticmethod
    def can_view_athlete_data(viewer, athlete) -> bool:
        """
        ¿Puede `viewer` ver los datos de `athlete`?
        Aplica a: nombre completo, email, teléfono, foto.
        No aplica a CURP, datos médicos o medidas (tienen métodos separados).
        """
        if viewer == athlete:
            return True

        if AccountPermissions._is_admin(viewer):
            return True

        # Coach/HEADCOACH: solo sus owned athletes
        if AccountPermissions._is_coach(viewer):
            return AccountPermissions._owns_user(viewer, athlete)

        # GUARDIAN: solo sus atletas asignados
        if viewer.roles.filter(name="GUARDIAN").exists():
            return AccountPermissions._is_guardian_of(viewer, athlete)

        return False

    @staticmethod
    def can_view_curp(viewer, target_user) -> bool:
        """CURP: solo admin y el propio usuario."""
        if viewer == target_user:
            return True
        return AccountPermissions._is_admin(viewer)

    @staticmethod
    def can_view_medical_data(viewer, athlete) -> bool:
        """
        Datos médicos: admin, HEADCOACH dueño, guardian del atleta.
        COACH asistente y STAFF no tienen acceso.
        """
        if viewer == athlete:
            return True

        if AccountPermissions._is_admin(viewer):
            return True

        if viewer.roles.filter(name="HEADCOACH").exists():
            return AccountPermissions._owns_user(viewer, athlete)

        if viewer.roles.filter(name="GUARDIAN").exists():
            return AccountPermissions._is_guardian_of(viewer, athlete)

        return False

    @staticmethod
    def can_view_measurements(viewer, athlete) -> bool:
        """
        Medidas corporales: admin, coach dueño, guardian del atleta.
        En Events: también JUEZ si el atleta tiene share_measurements_with_judges=True.
        """
        if viewer == athlete:
            return True

        if AccountPermissions._is_admin(viewer):
            return True

        if AccountPermissions._is_coach(viewer):
            return AccountPermissions._owns_user(viewer, athlete)

        if viewer.roles.filter(name="GUARDIAN").exists():
            return AccountPermissions._is_guardian_of(viewer, athlete)

        # JUEZ: solo si el atleta habilitó compartir medidas
        if viewer.roles.filter(name="JUEZ").exists():
            try:
                return athlete.privacy_settings.share_measurements_with_judges
            except Exception:
                return False

        return False

    # =========================================================================
    # PERMISOS ADMINISTRATIVOS
    # =========================================================================

    @staticmethod
    def can_create_athletes(user) -> bool:
        """Solo ADMIN y HEADCOACH pueden crear atletas."""
        return (
            user.is_superuser
            or user.roles.filter(name__in=["ADMIN", "HEADCOACH"]).exists()
        )

    @staticmethod
    def can_import_csv(user) -> bool:
        """Solo ADMIN y HEADCOACH pueden importar CSV."""
        return AccountPermissions.can_create_athletes(user)

    @staticmethod
    def can_manage_team(user, team) -> bool:
        """¿Puede gestionar un equipo específico?"""
        if AccountPermissions._is_admin(user):
            return True
        return team.coach == user

    @staticmethod
    def can_manage_teams(user) -> bool:
        """ADMIN y HEADCOACH pueden crear/editar/eliminar equipos y categorías."""
        return (
            user.is_superuser
            or user.roles.filter(name__in=["ADMIN", "HEADCOACH"]).exists()
        )

    @staticmethod
    def can_reassign_ownership(user) -> bool:
        """Solo ADMIN puede reasignar ownership entre coaches."""
        return user.is_superuser or user.roles.filter(name="ADMIN").exists()

    # =========================================================================
    # HELPERS PRIVADOS
    # =========================================================================

    @staticmethod
    def _is_admin(user) -> bool:
        return user.is_superuser or user.roles.filter(name="ADMIN").exists()

    @staticmethod
    def _is_coach(user) -> bool:
        return user.roles.filter(name__in=["HEADCOACH", "COACH"]).exists()

    @staticmethod
    def _owns_user(owner, user) -> bool:
        from accounts.models import UserOwnership

        return UserOwnership.objects.filter(
            owner=owner,
            user=user,
            is_active=True,
        ).exists()

    @staticmethod
    def _is_guardian_of(guardian, athlete) -> bool:
        try:
            return athlete.athleteprofile.guardian == guardian
        except Exception:
            return False

    @staticmethod
    def _share_team(user_a, user_b) -> bool:
        """¿Comparten al menos un equipo activo?"""
        from teams.models import UserTeamMembership

        teams_a = set(
            UserTeamMembership.objects.filter(
                user=user_a, is_active=True, status="accepted"
            ).values_list("team_id", flat=True)
        )
        teams_b = set(
            UserTeamMembership.objects.filter(
                user=user_b, is_active=True, status="accepted"
            ).values_list("team_id", flat=True)
        )
        return bool(teams_a & teams_b)

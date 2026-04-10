# accounts/services/ownership_service.py
"""
Servicio para gestión de UserOwnership (relación coach → usuario).

Centraliza toda la lógica de:
- Agregar usuarios (atletas/staff) a la propiedad de un coach
- Remover usuarios del ownership
- Transferir ownership entre coaches
- Queries de conveniencia

Principio de diseño: Las views solo orquestan, la lógica vive aquí.
Esto permite testear la lógica sin HTTP.
"""

import logging
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import transaction
from django.utils import timezone

from accounts.models import UserOwnership
from teams.models import UserTeamMembership

logger = logging.getLogger(__name__)
User = get_user_model()


class OwnershipService:
    """
    Gestiona la relación de propiedad entre coaches y sus atletas/staff.

    ¿Por qué UserOwnership en lugar de solo TeamMembership?
    Porque un atleta puede pertenecer al coach sin estar en un equipo activo.
    Es la relación administrativa (quién puede editar, ver sus medidas, etc.)
    mientras que TeamMembership es la relación deportiva.
    """

    # =========================================================================
    # AGREGAR USUARIO AL OWNERSHIP
    # =========================================================================

    @staticmethod
    @transaction.atomic
    def add_to_ownership(
        *, owner: User, user: User, activated_by: User
    ) -> UserOwnership:
        """
        Agrega un usuario al ownership de un coach.

        Parámetros:
            owner: El coach que adquiere la propiedad
            user: El usuario a agregar (atleta o staff)
            activated_by: Quien ejecuta la operación (para auditoría)

        Retorna:
            UserOwnership creado o reactivado (idempotente)

        Lanza:
            ValidationError si las reglas de negocio no se cumplen
            PermissionDenied si activated_by no tiene permisos
        """
        OwnershipService._validate_can_manage_ownership(activated_by, owner)
        OwnershipService._validate_owner_is_coach(owner)
        OwnershipService._validate_not_self(owner, user)

        # --- Verificar si ya existe un ownership activo ---
        existing = UserOwnership.objects.filter(
            owner=owner,
            user=user,
            is_active=True,
        ).first()

        if existing:
            # Idempotente: ya existe, no hacer nada
            logger.debug("Ownership ya existe: %s → %s (sin cambios)", owner, user)
            return existing

        # --- Verificar si existe inactivo (reactivar en lugar de crear) ---
        inactive = (
            UserOwnership.objects.filter(
                owner=owner,
                user=user,
                is_active=False,
            )
            .order_by("-created_at")
            .first()
        )

        if inactive:
            inactive.is_active = True
            inactive.deactivated_at = None
            inactive.save(update_fields=["is_active", "deactivated_at"])

            logger.info(
                "Ownership reactivado: %s → %s por %s",
                owner,
                user,
                activated_by,
            )
            return inactive

        # --- Crear nuevo ownership ---
        ownership = UserOwnership.objects.create(
            owner=owner,
            user=user,
            is_active=True,
        )

        logger.info(
            "Ownership creado: %s → %s por %s",
            owner,
            user,
            activated_by,
        )

        return ownership

    # =========================================================================
    # REMOVER USUARIO DEL OWNERSHIP
    # =========================================================================

    @staticmethod
    @transaction.atomic
    def remove_from_ownership(*, ownership_id: int, removed_by: User) -> UserOwnership:
        """
        Desactiva un ownership (soft delete).
        También desactiva las membresías de equipo del usuario
        en equipos controlados por el coach.

        El ownership desactivado se mantiene en BD para auditoría.
        """
        try:
            ownership = UserOwnership.objects.select_related("owner", "user").get(
                id=ownership_id, is_active=True
            )
        except UserOwnership.DoesNotExist:
            raise ValidationError(
                f"Ownership #{ownership_id} no encontrado o ya inactivo."
            )

        OwnershipService._validate_can_manage_ownership(removed_by, ownership.owner)

        # --- Desactivar ownership ---
        ownership.is_active = False
        ownership.deactivated_at = timezone.now()
        ownership.save(update_fields=["is_active", "deactivated_at"])

        # --- Desactivar membresías en equipos del coach ---
        affected_memberships = UserTeamMembership.objects.filter(
            user=ownership.user,
            team__coach=ownership.owner,
            is_active=True,
        )

        count = affected_memberships.count()
        affected_memberships.update(
            is_active=False,
            status="inactive",
            end_date=timezone.now().date(),
        )

        logger.info(
            "Ownership desactivado: %s → %s por %s. Membresías desactivadas: %d",
            ownership.owner,
            ownership.user,
            removed_by,
            count,
        )

        return ownership

    # =========================================================================
    # TRANSFERIR OWNERSHIP
    # =========================================================================

    @staticmethod
    @transaction.atomic
    def transfer_ownership(
        *, ownership_id: int, new_owner: User, transferred_by: User
    ) -> UserOwnership:
        """
        Transfiere un usuario de un coach a otro.
        Solo ADMIN puede hacer esto.

        El ownership antiguo se desactiva, se crea uno nuevo.
        """
        if (
            not transferred_by.is_superuser
            and not transferred_by.roles.filter(name="ADMIN").exists()
        ):
            raise PermissionDenied("Solo administradores pueden transferir ownerships.")

        OwnershipService._validate_owner_is_coach(new_owner)

        try:
            old_ownership = UserOwnership.objects.select_related("owner", "user").get(
                id=ownership_id, is_active=True
            )
        except UserOwnership.DoesNotExist:
            raise ValidationError(f"Ownership #{ownership_id} no encontrado.")

        if old_ownership.owner == new_owner:
            raise ValidationError("El nuevo owner es el mismo que el actual.")

        user = old_ownership.user

        # --- Desactivar el ownership anterior ---
        old_ownership.is_active = False
        old_ownership.deactivated_at = timezone.now()
        old_ownership.save(update_fields=["is_active", "deactivated_at"])

        # --- Crear nuevo ownership ---
        new_ownership = UserOwnership.objects.create(
            owner=new_owner,
            user=user,
            is_active=True,
        )

        logger.info(
            "Ownership transferido: %s → %s (antes era de %s) por %s",
            new_owner,
            user,
            old_ownership.owner,
            transferred_by,
        )

        return new_ownership

    # =========================================================================
    # QUERIES
    # =========================================================================

    @staticmethod
    def get_owned_athletes(coach: User):
        """
        Retorna atletas activos owned por el coach.
        """
        return User.objects.filter(
            owner_links__owner=coach,
            owner_links__is_active=True,
            roles__name="ATHLETE",
        ).distinct()

    @staticmethod
    def get_owned_staff(coach: User):
        """
        Retorna staff activo owned por el coach.
        """
        return User.objects.filter(
            owner_links__owner=coach,
            owner_links__is_active=True,
            roles__name__in=["COACH", "STAFF"],
        ).distinct()

    @staticmethod
    def get_all_owned_users(coach: User):
        """
        Retorna todos los usuarios activos owned por el coach.
        Con prefetch para performance.
        """
        return (
            User.objects.filter(
                owner_links__owner=coach,
                owner_links__is_active=True,
            )
            .prefetch_related(
                "roles",
                "team_memberships__team",
            )
            .distinct()
        )

    @staticmethod
    def is_owned_by(owner: User, user: User) -> bool:
        """
        Verifica si un usuario pertenece al ownership de un coach.
        """
        return UserOwnership.objects.filter(
            owner=owner,
            user=user,
            is_active=True,
        ).exists()

    # =========================================================================
    # HELPERS PRIVADOS
    # =========================================================================

    @staticmethod
    def _validate_can_manage_ownership(manager: User, owner: User):
        """
        Verifica que el manager puede gestionar el ownership del owner.
        - Admin: puede gestionar cualquier ownership
        - HEADCOACH: solo puede gestionar su propio ownership
        """
        if manager.is_superuser or manager.roles.filter(name="ADMIN").exists():
            return

        # HEADCOACH gestionando su propio ownership
        if manager == owner:
            if manager.roles.filter(name="HEADCOACH").exists():
                return

        raise PermissionDenied("No tienes permisos para gestionar este ownership.")

    @staticmethod
    def _validate_owner_is_coach(owner: User):
        """
        Verifica que el owner tiene un rol de coach.
        """
        is_coach = (
            owner.is_superuser
            or owner.roles.filter(name__in=["HEADCOACH", "ADMIN"]).exists()
        )

        if not is_coach:
            raise ValidationError(
                f"El usuario {owner} no tiene rol de coach/admin "
                "y no puede ser owner de otros usuarios."
            )

    @staticmethod
    def _validate_not_self(owner: User, user: User):
        """
        Un usuario no puede ser su propio owned.
        """
        if owner == user:
            raise ValidationError("Un usuario no puede ser su propio 'owned'.")

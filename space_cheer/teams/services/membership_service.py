import logging
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import QuerySet

from teams.models import Team, UserTeamMembership

logger = logging.getLogger(__name__)
User = get_user_model()


class MembershipService:

    @staticmethod
    @transaction.atomic
    def add_member(*, team: Team, user, role: str, added_by) -> UserTeamMembership:
        """
        Agrega un usuario al equipo con el rol indicado.
        Si ya existe una membresía inactiva, la reactiva en lugar de crear duplicado.
        Lanza ValidationError si el usuario ya es miembro activo.
        """
        existing = UserTeamMembership.objects.filter(user=user, team=team).first()

        if existing:
            if existing.is_active and existing.status == "accepted":
                raise ValidationError(
                    f"{user.get_full_name() or user.username} ya es miembro activo de {team.name}."
                )
            existing.activate(role=role)
            logger.info(
                "Membresía reactivada: %s → %s (rol=%s) por %s",
                user,
                team.name,
                role,
                added_by,
            )
            return existing

        membership = UserTeamMembership.objects.create(
            user=user,
            team=team,
            role_in_team=role,
            status="accepted",
            is_active=True,
        )
        logger.info(
            "Membresía creada: %s → %s (rol=%s) por %s",
            user,
            team.name,
            role,
            added_by,
        )
        return membership

    @staticmethod
    @transaction.atomic
    def remove_member(*, membership: UserTeamMembership, removed_by) -> UserTeamMembership:
        """
        Desactiva una membresía (soft delete con fecha de fin).
        """
        membership.deactivate()
        logger.info(
            "Membresía desactivada: %s → %s por %s",
            membership.user,
            membership.team.name,
            removed_by,
        )
        return membership

    @staticmethod
    def get_available_users(*, team: Team, requesting_user) -> QuerySet:
        """
        Retorna usuarios que pueden agregarse al equipo según el rol del solicitante.
        - ADMIN: todos los usuarios del sistema no activos en el equipo.
        - HEADCOACH: solo sus usuarios owned (atletas + crew) no activos.
        Excluye siempre al coach del equipo (ya está como dueño).
        """
        already_active_ids = (
            team.memberships
            .filter(is_active=True, status="accepted")
            .values_list("user_id", flat=True)
        )

        qs = (
            User.objects
            .exclude(id__in=already_active_ids)
            .exclude(id=team.coach_id)
        )

        is_admin = (
            requesting_user.is_superuser
            or requesting_user.roles.filter(name="ADMIN").exists()
        )

        if not is_admin:
            qs = qs.filter(
                owner_links__owner=requesting_user,
                owner_links__is_active=True,
            )

        return qs.order_by("first_name").distinct()

import logging
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import QuerySet

from teams.models import Team, UserTeamMembership
from accounts.tasks import notify_team_join_request, notify_join_decision

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
            MembershipService._grant_coach_role_if_needed(user=user, role=role)
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
        MembershipService._grant_coach_role_if_needed(user=user, role=role)
        return membership

    @staticmethod
    def _grant_coach_role_if_needed(*, user, role: str):
        """Si se agrega como COACH, otorga el rol global COACH y aprueba su CoachProfile."""
        if role != "COACH":
            return
        from accounts.models import Role, CoachProfile

        coach_role, _ = Role.objects.get_or_create(
            name="COACH", defaults={"is_coach_type": True, "requires_curp": True}
        )
        user.roles.add(coach_role)  # signal crea CoachProfile(PENDING) si no existe
        profile, _ = CoachProfile.objects.get_or_create(user=user)
        if profile.approval_status != CoachProfile.APPROVED:
            profile.approval_status = CoachProfile.APPROVED
            profile.save(update_fields=["approval_status"])

    @staticmethod
    @transaction.atomic
    def remove_member(*, membership: UserTeamMembership, removed_by) -> UserTeamMembership:
        """Baja suave de una membresía. Para atletas, desactiva también el UserOwnership
        con el coach del equipo. El rol global del usuario se conserva."""
        from accounts.models import UserOwnership

        membership.deactivate()
        if membership.role_in_team == "ATHLETE":
            UserOwnership.objects.filter(
                owner=membership.team.coach,
                user=membership.user,
                is_active=True,
            ).update(is_active=False)
        logger.info(
            "Membresía desactivada: %s → %s por %s",
            membership.user,
            membership.team.name,
            removed_by,
        )
        return membership

    @staticmethod
    @transaction.atomic
    def request_join_by_code(*, user, code: str) -> UserTeamMembership:
        """Crea una solicitud de unión (pending) a partir del código del equipo."""
        normalized = (code or "").strip().upper()
        team = Team.objects.filter(join_code=normalized, is_active=True).first()
        if team is None:
            raise ValidationError("Código de equipo inválido o equipo inactivo.")

        existing = UserTeamMembership.objects.filter(user=user, team=team).first()
        if existing:
            if existing.is_active and existing.status == "accepted":
                raise ValidationError(f"Ya eres miembro de {team.name}.")
            if existing.status == "pending":
                raise ValidationError("Ya tienes una solicitud pendiente para este equipo.")
            # rechazada/inactiva: reabrir como pending
            existing.status = "pending"
            existing.is_active = False
            existing.role_in_team = "ATHLETE"
            existing.save(update_fields=["status", "is_active", "role_in_team"])
            membership = existing
        else:
            membership = UserTeamMembership.objects.create(
                user=user, team=team, role_in_team="ATHLETE",
                status="pending", is_active=False,
            )
        logger.info("Solicitud de unión: %s → %s", user, team.name)
        notify_team_join_request.delay(membership.id)
        return membership

    @staticmethod
    @transaction.atomic
    def accept_request(*, membership: UserTeamMembership, by) -> UserTeamMembership:
        from accounts.models import UserOwnership

        membership.accept()  # status=accepted, is_active=True
        UserOwnership.objects.get_or_create(
            owner=membership.team.coach,
            user=membership.user,
            is_active=True,
            defaults={},
        )
        logger.info("Solicitud aceptada: %s → %s por %s", membership.user, membership.team.name, by)
        notify_join_decision.delay(membership.id, True)
        return membership

    @staticmethod
    @transaction.atomic
    def reject_request(*, membership: UserTeamMembership, by) -> UserTeamMembership:
        membership.reject()  # status=rejected, is_active=False
        logger.info("Solicitud rechazada: %s → %s por %s", membership.user, membership.team.name, by)
        notify_join_decision.delay(membership.id, False)
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

from accounts.models import AthleteProfile
from teams.models import UserTeamMembership


class MinorAccessService:
    BLOCKED = "BLOCKED"
    READ_ONLY = "READ_ONLY"
    ACTIVE = "ACTIVE"

    @staticmethod
    def get_access_level(user) -> str | None:
        """
        Calcula el nivel de acceso de un atleta menor.
        Retorna None si el usuario no es menor de edad.

        BLOCKED   → menor sin guardian asignado
        READ_ONLY → guardian asignado, sin equipo activo
        ACTIVE    → guardian asignado + equipo activo
        """
        if not user.is_minor:
            return None

        try:
            profile = AthleteProfile.objects.select_related("guardian").get(user=user)
            if profile.guardian is None:
                return MinorAccessService.BLOCKED
        except AthleteProfile.DoesNotExist:
            return MinorAccessService.BLOCKED

        has_active_team = UserTeamMembership.objects.filter(
            user=user,
            is_active=True,
            status="accepted",
        ).exists()

        return MinorAccessService.ACTIVE if has_active_team else MinorAccessService.READ_ONLY

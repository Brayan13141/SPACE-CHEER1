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

        BLOCKED   → menor sin NINGÚN tutor acreditado
        READ_ONLY → al menos un tutor, sin equipo activo
        ACTIVE    → al menos un tutor + equipo activo
        """
        from custody.models import Guardianship

        if not user.is_minor:
            return None

        if not AthleteProfile.objects.filter(user=user).exists():
            return MinorAccessService.BLOCKED

        if not Guardianship.objects.filter(athlete=user).exists():
            return MinorAccessService.BLOCKED

        has_active_team = UserTeamMembership.objects.filter(
            user=user,
            is_active=True,
            status="accepted",
        ).exists()

        return MinorAccessService.ACTIVE if has_active_team else MinorAccessService.READ_ONLY

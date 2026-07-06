"""Servicios de perfil y visibilidad del portal social."""

from social.models import SocialProfile


class SocialProfileService:
    @staticmethod
    def for_user(user):
        """Devuelve el SocialProfile del usuario, creándolo con defaults si falta.

        Toda vista/servicio social debe pasar por aquí — nunca acceder a
        user.social_profile directo (RelatedObjectDoesNotExist → 500).
        """
        profile, _created = SocialProfile.objects.get_or_create(user=user)
        return profile


class SocialVisibilityService:
    @staticmethod
    def _is_admin(user):
        return user.is_superuser or user.roles.filter(name="ADMIN").exists()

    @staticmethod
    def shares_active_team(user_a, user_b):
        from teams.models import UserTeamMembership

        teams_a = UserTeamMembership.objects.filter(
            user=user_a, is_active=True
        ).values("team_id")
        return UserTeamMembership.objects.filter(
            user=user_b, is_active=True, team_id__in=teams_a
        ).exists()

    @staticmethod
    def can_view_profile(viewer, owner):
        """Perfil social visible según profile_visibility. False → la vista da 404
        (mismo 404 que 'no existe': no filtrar existencia de perfiles privados)."""
        if not owner.is_active:
            return False
        if viewer.pk == owner.pk or SocialVisibilityService._is_admin(viewer):
            return True
        profile = SocialProfileService.for_user(owner)
        if profile.profile_visibility == SocialProfile.Visibility.PLATFORM:
            return True
        return SocialVisibilityService.shares_active_team(viewer, owner)

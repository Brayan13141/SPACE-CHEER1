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

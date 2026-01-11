from django.db.models.signals import post_save, m2m_changed
from django.dispatch import receiver
from django.conf import settings

from .models import (
    CoachProfile,
    Role,
    StaffProfile,
    User,
    AthleteProfile,
    AthleteMedicalInfo,
)


# -----------------------------------------------------------
# 1. Crear perfiles automáticos cuando se asigna un rol
# -----------------------------------------------------------
@receiver(m2m_changed, sender=User.roles.through)
def create_role_profiles(sender, instance, action, pk_set, **kwargs):
    if action != "post_add":
        return

    roles = Role.objects.filter(pk__in=pk_set)

    for role in roles:
        role_name = role.name.lower()

        if role_name == "atleta":
            athlete_profile, _ = AthleteProfile.objects.get_or_create(user=instance)
            AthleteMedicalInfo.objects.get_or_create(athlete=athlete_profile)

        if role_name == "coach":
            CoachProfile.objects.get_or_create(user=instance)

        if role_name == "apoyo":
            StaffProfile.objects.get_or_create(user=instance)

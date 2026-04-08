import logging

from django.db.models.signals import m2m_changed, post_save
from django.dispatch import receiver

from .models import (
    CoachProfile,
    Role,
    StaffProfile,
    User,
    AthleteProfile,
    AthleteMedicalInfo,
)

logger = logging.getLogger("space_cheer")


@receiver(m2m_changed, sender=User.roles.through)
def create_role_profiles(sender, instance, action, pk_set, **kwargs):
    if action != "post_add":
        return

    try:
        roles = Role.objects.filter(pk__in=pk_set)
    except Exception:
        logger.error(
            "Error obteniendo roles para usuario_id=%s con pk_set=%s",
            instance.id,
            pk_set,
            exc_info=True,
        )
        return

    for role in roles:
        role_name = role.name.lower()

        # -----------------------------
        # ATLETA
        # -----------------------------
        if role_name == "atleta":
            try:
                athlete_profile, created = AthleteProfile.objects.get_or_create(
                    user=instance
                )
                logger.info(
                    "AthleteProfile %s para usuario_id=%s",
                    "creado" if created else "existente",
                    instance.id,
                )

                medical_info, med_created = AthleteMedicalInfo.objects.get_or_create(
                    athlete=athlete_profile
                )
                logger.info(
                    "AthleteMedicalInfo %s para usuario_id=%s",
                    "creado" if med_created else "existente",
                    instance.id,
                )

            except Exception:
                logger.error(
                    "Error creando perfil de atleta para usuario_id=%s",
                    instance.id,
                    exc_info=True,
                )

        # -----------------------------
        # COACH
        # -----------------------------
        elif role_name == "coach":
            try:
                profile, created = CoachProfile.objects.get_or_create(user=instance)
                logger.info(
                    "CoachProfile %s para usuario_id=%s",
                    "creado" if created else "existente",
                    instance.id,
                )
            except Exception:
                logger.error(
                    "Error creando perfil de coach para usuario_id=%s",
                    instance.id,
                    exc_info=True,
                )

        # -----------------------------
        # STAFF
        # -----------------------------
        elif role_name == "staff":
            try:
                profile, created = StaffProfile.objects.get_or_create(user=instance)
                logger.info(
                    "StaffProfile %s para usuario_id=%s",
                    "creado" if created else "existente",
                    instance.id,
                )
            except Exception:
                logger.error(
                    "Error creando perfil de staff para usuario_id=%s",
                    instance.id,
                    exc_info=True,
                )
        # -----------------------------
        # GUARDIAN
        # -----------------------------
        elif role_name == "guardian":
            try:
                from accounts.models import GuardianProfile

                profile, created = GuardianProfile.objects.get_or_create(user=instance)

                logger.info(
                    "GuardianProfile %s para usuario_id=%s",
                    "creado" if created else "existente",
                    instance.id,
                )

            except Exception:
                logger.error(
                    "Error creando perfil de guardian para usuario_id=%s",
                    instance.id,
                    exc_info=True,
                )
        else:
            logger.warning(
                "Rol desconocido '%s' para usuario_id=%s",
                role.name,
                instance.id,
            )


@receiver(post_save, sender=User)
def create_user_preferences(sender, instance, created, **kwargs):
    if created:
        from accounts.models import NotificationPreferences, PrivacySettings

        NotificationPreferences.objects.get_or_create(user=instance)
        PrivacySettings.objects.get_or_create(user=instance)

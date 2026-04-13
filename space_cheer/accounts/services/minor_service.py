# accounts/services/minor_service.py
"""
Servicio para gestión de atletas menores de edad.

Reglas de negocio:
- Un atleta menor DEBE tener un tutor/guardian asignado
- El coach que posee al atleta puede asignar/cambiar el guardian
- El guardian debe existir en el sistema con perfil GuardianProfile o puede ser otro usuario
- Si el atleta cumple 18 años, se puede desactivar el guardian (no es obligatorio)
- Un guardian puede tener múltiples atletas bajo su custodia

Flujo completo:
1. Coach crea atleta menor → sistema detecta is_minor = True
2. Coach asigna guardian al atleta (puede ser padre ya registrado o crea uno nuevo)
3. Sistema crea GuardianProfile para el guardian si no existe
4. Se notifica al guardian (email)
"""

import logging
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

# Importamos modelos de accounts — ciclo de import seguro porque estamos en el mismo app
from accounts.models import (
    AthleteProfile,
    GuardianProfile,
    UserOwnership,
    Role,
)

logger = logging.getLogger(__name__)
User = get_user_model()


class MinorAthleteService:
    """
    Gestiona el ciclo de vida de atletas menores de edad:
    - Validación de edad
    - Asignación y remoción de guardian
    - Verificación de compliance (menor sin guardian = bloqueado)
    """

    # =========================================================================
    # VALIDACIONES PÚBLICAS
    # =========================================================================

    @staticmethod
    def is_minor(user: User) -> bool:
        """
        Determina si un usuario es menor de edad.
        Retorna False si no tiene fecha de nacimiento registrada.
        La lógica está aquí (no en el modelo) para poder mockearla en tests.
        """
        if not user.birth_date:
            return False

        today = timezone.now().date()
        # Cálculo correcto de edad considerando si ya cumplió años este año
        age = (
            today.year
            - user.birth_date.year
            - ((today.month, today.day) < (user.birth_date.month, user.birth_date.day))
        )
        return age < 18

    @staticmethod
    def requires_guardian(athlete: User) -> bool:
        """
        Retorna True si el atleta es menor Y no tiene guardian asignado.
        Esto define si el sistema debe bloquear ciertas operaciones.
        """
        if not MinorAthleteService.is_minor(athlete):
            return False

        try:
            profile = athlete.athleteprofile
            return profile.guardian is None
        except AthleteProfile.DoesNotExist:
            # Sin perfil de atleta = sin guardian por definición
            return True

    @staticmethod
    def get_guardian(athlete: User):
        """
        Retorna el guardian del atleta o None si no tiene.
        Lanza ValidationError si el atleta no tiene perfil de atleta.
        """
        try:
            return athlete.athleteprofile.guardian
        except AthleteProfile.DoesNotExist:
            raise ValidationError(f"El usuario {athlete} no tiene perfil de atleta.")

    # =========================================================================
    # ASIGNACIÓN DE GUARDIAN
    # =========================================================================

    @staticmethod
    @transaction.atomic
    def assign_guardian(
        *, athlete: User, guardian: User, assigned_by: User
    ) -> AthleteProfile:
        """
        Asigna un guardian a un atleta menor.

        Parámetros:
            athlete: El atleta menor al que se asigna el guardian
            guardian: El usuario que será guardian
            assigned_by: El coach/admin que hace la asignación

        Retorna:
            AthleteProfile actualizado

        Lanza:
            ValidationError si las reglas de negocio no se cumplen
            PermissionDenied si el usuario no tiene permiso
        """
        # --- Validar que quien asigna tiene permisos ---
        MinorAthleteService._validate_can_manage_athlete(assigned_by, athlete)

        # --- Validar que el atleta tiene perfil ---
        try:
            profile = athlete.athleteprofile
        except AthleteProfile.DoesNotExist:
            raise ValidationError(
                f"El atleta {athlete} no tiene perfil de atleta. "
                "Crea el perfil primero."
            )

        # --- Validar que el atleta es menor ---
        if not MinorAthleteService.is_minor(athlete):
            raise ValidationError(
                f"El atleta {athlete} no es menor de edad. "
                "Los guardians solo se asignan a menores."
            )

        # --- Validar que el guardian no sea el mismo atleta ---
        if guardian == athlete:
            raise ValidationError("Un atleta no puede ser su propio guardian.")

        # --- Validar que el guardian no sea menor también ---
        if MinorAthleteService.is_minor(guardian):
            raise ValidationError(
                f"El usuario {guardian} también es menor de edad "
                "y no puede ser guardian."
            )

        # --- Crear GuardianProfile si no existe ---
        guardian_profile, created = GuardianProfile.objects.get_or_create(
            user=guardian,
            defaults={
                "relation": "ACOMP"
            },  # relación por defecto, coach puede cambiarla
        )

        if created:
            logger.info(
                "GuardianProfile creado para %s asignado como guardian de %s por %s",
                guardian,
                athlete,
                assigned_by,
            )

        # --- Asignar guardian al perfil del atleta ---
        old_guardian = profile.guardian
        profile.guardian = guardian
        profile.save(update_fields=["guardian"])

        logger.info(
            "Guardian %s asignado a atleta menor %s (antes: %s) por %s",
            guardian,
            athlete,
            old_guardian,
            assigned_by,
        )

        return profile

    @staticmethod
    @transaction.atomic
    def remove_guardian(*, athlete: User, removed_by: User) -> AthleteProfile:
        """
        Remueve el guardian de un atleta.

        IMPORTANTE: Solo se permite si el atleta ya es mayor de edad.
        Si sigue siendo menor, el guardian es obligatorio.

        Lanza:
            ValidationError si el atleta sigue siendo menor
        """
        MinorAthleteService._validate_can_manage_athlete(removed_by, athlete)

        try:
            profile = athlete.athleteprofile
        except AthleteProfile.DoesNotExist:
            raise ValidationError("El atleta no tiene perfil.")

        # --- Bloquear si sigue siendo menor ---
        if MinorAthleteService.is_minor(athlete):
            raise ValidationError(
                f"No se puede remover el guardian de {athlete} porque sigue siendo menor de edad. "
                "El guardian es obligatorio para menores."
            )

        if profile.guardian is None:
            return profile  # Idempotente: ya no tiene guardian

        old_guardian = profile.guardian
        profile.guardian = None
        profile.save(update_fields=["guardian"])

        logger.info(
            "Guardian %s removido de atleta %s (ahora mayor de edad) por %s",
            old_guardian,
            athlete,
            removed_by,
        )

        return profile

    @staticmethod
    def update_guardian_relation(
        *, athlete: User, relation: str, updated_by: User
    ) -> GuardianProfile:
        """
        Actualiza el tipo de relación del guardian (PADRE, TUTOR, ACOMP).

        Retorna el GuardianProfile actualizado.
        """
        VALID_RELATIONS = {"PADRE", "TUTOR", "ACOMP"}

        if relation not in VALID_RELATIONS:
            raise ValidationError(
                f"Relación inválida: {relation}. Opciones: {VALID_RELATIONS}"
            )

        MinorAthleteService._validate_can_manage_athlete(updated_by, athlete)

        guardian = MinorAthleteService.get_guardian(athlete)
        if guardian is None:
            raise ValidationError(f"El atleta {athlete} no tiene guardian asignado.")

        try:
            gp = guardian.guardianprofile
        except GuardianProfile.DoesNotExist:
            raise ValidationError(f"El guardian {guardian} no tiene GuardianProfile.")

        gp.relation = relation
        gp.save(update_fields=["relation"])

        return gp

    # =========================================================================
    # QUERIES DE CONVENIENCIA
    # =========================================================================
    @staticmethod
    def get_minors_without_guardian(coach: User):

        owned_ids = UserOwnership.objects.filter(
            owner=coach,
            is_active=True,
        ).values_list("user_id", flat=True)

        today = timezone.now().date()

        cutoff_date = today.replace(year=today.year - 18)

        if coach.is_superuser or coach.roles.filter(name="ADMIN").exists():

            return (
                User.objects.filter(
                    roles__name="ATHLETE",
                    birth_date__isnull=False,
                    birth_date__lte=today,
                    birth_date__gt=cutoff_date,
                )
                .filter(
                    Q(athleteprofile__isnull=True)
                    | Q(athleteprofile__guardian__isnull=True)
                )
                .select_related("athleteprofile")
                .distinct()
            )
        elif coach.roles.filter(name="HEADCOACH").exists():
            return (
                User.objects.filter(
                    id__in=owned_ids,
                    roles__name="ATHLETE",
                    birth_date__isnull=False,
                    birth_date__lte=today,  # Aseguramos que no incluya futuros
                    birth_date__gt=cutoff_date,
                )
                .filter(
                    Q(athleteprofile__isnull=True)
                    | Q(athleteprofile__guardian__isnull=True)
                )
                .select_related("athleteprofile")
                .distinct()
            )
        else:
            raise PermissionDenied("No tienes permisos para ver esta información.")

    @staticmethod
    def get_athletes_for_guardian(guardian: User):
        """
        Retorna todos los atletas que tienen a este usuario como guardian.
        """
        return User.objects.filter(athleteprofile__guardian=guardian).select_related(
            "athleteprofile"
        )

    # =========================================================================
    # HELPERS PRIVADOS
    # =========================================================================

    @staticmethod
    def _validate_can_manage_athlete(manager: User, athlete: User):
        """
        Verifica que `manager` tiene permiso para gestionar al `athlete`.
        Reglas:
        - Admin/superuser → siempre puede
        - HEADCOACH → solo atletas que le pertenecen (UserOwnership)
        """
        if manager.is_superuser:
            return

        if manager.roles.filter(name="ADMIN").exists():
            return

        # HEADCOACH: verificar ownership
        if manager.roles.filter(name="HEADCOACH").exists():
            owns = UserOwnership.objects.filter(
                owner=manager,
                user=athlete,
                is_active=True,
            ).exists()

            if not owns:
                raise PermissionDenied(
                    f"No tienes permiso para gestionar al atleta {athlete}."
                )
            return

        raise PermissionDenied("No tienes permisos para gestionar atletas.")

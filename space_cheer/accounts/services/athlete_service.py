import logging
from django.contrib.auth import get_user_model
from django.db import models, transaction
from django.db.models import Max
from django.utils.crypto import get_random_string

from accounts.models import AthleteProfile, AthleteMedicalInfo, Role, UserOwnership
from accounts.services.ownership_service import OwnershipService

logger = logging.getLogger(__name__)
User = get_user_model()


class AthleteService:
    """Alta rápida de atletas desde el panel de coach (sin flujo de registro completo)."""

    @staticmethod
    @transaction.atomic
    def create_quick(
        *,
        first_name: str,
        last_name: str,
        email: str = "",
        phone: str = "",
        created_by,
    ) -> tuple:
        """
        Crea un atleta rápidamente desde la interfaz del coach.

        Pasos:
        1. Genera username incremental seguro (ATLETA-N)
        2. Genera contraseña temporal aleatoria (única por atleta)
        3. Crea el User
        4. Asigna el rol global ATLETA
        5. Crea AthleteProfile con valores mínimos
        6. Crea AthleteMedicalInfo vacío
        7. Registra ownership: created_by → nuevo usuario

        Retorna (user, temp_password).
        Lanza ValueError o Role.DoesNotExist si los datos de configuración faltan.
        """
        username = AthleteService._generate_username()
        temp_password = get_random_string(
            length=12,
            allowed_chars="abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ23456789",
        )

        user = User.objects.create_user(
            username=username,
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            password=temp_password,
            profile_completed=True,
        )

        user.roles.add(Role.objects.get(name="ATHLETE"))

        athlete_profile, _ = AthleteProfile.objects.get_or_create(
            user=user,
            defaults={
                "emergency_contact": "POR DEFINIR",
                "emergency_phone": "",
            },
        )

        AthleteMedicalInfo.objects.get_or_create(athlete=athlete_profile)

        OwnershipService.add_to_ownership(
            owner=created_by,
            user=user,
            activated_by=created_by,
        )

        logger.info(
            "Atleta creado rápido: %s (creado por %s)",
            username,
            created_by,
        )
        return user, temp_password

    @staticmethod
    def _generate_username() -> str:
        """
        Genera el próximo username ATLETA-N libre.
        Usa MAX para evitar race conditions en entornos multi-proceso.
        La transacción atómica del caller garantiza consistencia.
        """
        max_num = (
            User.objects.filter(username__startswith="ATLETA-")
            .annotate(
                num=models.functions.Cast(
                    models.functions.Substr("username", 8),
                    models.IntegerField(),
                )
            )
            .aggregate(max_num=Max("num"))["max_num"]
        ) or 0

        return f"ATLETA-{max_num + 1}"

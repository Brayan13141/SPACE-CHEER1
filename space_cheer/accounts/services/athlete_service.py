import logging
from django.contrib.auth import get_user_model
from django.db import models, transaction
from django.db.models import Max

from decouple import config

from accounts.models import AthleteProfile, AthleteMedicalInfo, Role, UserOwnership
from accounts.services.ownership_service import OwnershipService

logger = logging.getLogger(__name__)
User = get_user_model()


class AthleteService:

    @staticmethod
    @transaction.atomic
    def create_quick(
        *,
        first_name: str,
        last_name: str,
        email: str = "",
        phone: str = "",
        created_by,
    ) -> User:
        """
        Crea un atleta rápidamente desde la interfaz del coach.

        Pasos:
        1. Genera username incremental seguro (ATLETA-N)
        2. Crea el User con contraseña temporal
        3. Asigna el rol global ATLETA
        4. Crea AthleteProfile con valores mínimos
        5. Crea AthleteMedicalInfo vacío
        6. Registra ownership: created_by → nuevo usuario

        Retorna el User creado.
        Lanza ValueError o Role.DoesNotExist si los datos de configuración faltan.
        """
        username = AthleteService._generate_username()

        user = User.objects.create_user(
            username=username,
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            password=config("ATLETA_TEMP_PASSWORD"),
            profile_completed=False,
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
        return user

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
                    models.functions.Substr("username", 9),
                    models.IntegerField(),
                )
            )
            .aggregate(max_num=Max("num"))["max_num"]
        ) or 0

        return f"ATLETA-{max_num + 1}"

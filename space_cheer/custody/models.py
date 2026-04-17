# custody/models.py
"""
Modelos para la gestión de custodia de atletas menores de edad.

GuardianProfile almacena el tipo de relación entre el guardian y el atleta.
La asignación concreta (quién es guardian de quién) vive en AthleteProfile.guardian (FK a User).
"""

from django.db import models
from django.conf import settings


class GuardianProfile(models.Model):
    """
    Perfil extendido para usuarios con rol GUARDIAN.

    Almacena el tipo de relación que tiene el guardian con el atleta.
    Se crea automáticamente via signal cuando se asigna el rol GUARDIAN a un User.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="guardianprofile",
    )

    relation = models.CharField(
        max_length=50,
        choices=[
            ("PADRE", "Padre / Madre"),
            ("TUTOR", "Tutor legal"),
            ("ACOMP", "Acompañante"),
        ],
        default="ACOMP",
    )

    def __str__(self):
        return f"Tutor/Acompañante: {self.user}"

    class Meta:
        verbose_name = "Perfil de Guardian"
        verbose_name_plural = "Perfiles de Guardian"

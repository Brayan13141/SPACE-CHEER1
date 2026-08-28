# custody/models.py
"""
Modelos para la gestión de custodia de atletas menores de edad.

Guardianship es el vínculo acreditado entre un atleta menor y un tutor.
Vive en el par, no en el usuario: la misma persona puede ser madre de una
atleta y tutora legal de otra, y cada vínculo se verifica por su cuenta.
Un atleta puede tener N tutores, todos con los mismos permisos: no hay
tutor "principal".

GuardianProfile (legacy) se mantiene por compatibilidad mientras migran
los consumidores; describe el tipo de relación del usuario y su verificación
global, pero ya no gobierna la asignación atleta-tutor.
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

    PADRE = "PADRE"
    TUTOR = "TUTOR"
    ACOMP = "ACOMP"

    RELATION_CHOICES = [
        (PADRE, "Padre / Madre"),
        (TUTOR, "Tutor legal"),
        (ACOMP, "Acompañante"),
    ]

    # Solo la tutela legal pide respaldo. `PADRE` y `ACOMP` son declarativos y
    # cubren la enorme mayoría de los casos; `TUTOR` es el que sostiene
    # decisiones sobre un menor cuando los padres no están, y ese sí no debería
    # quedar en la palabra de quien llena el formulario.
    RELATIONS_REQUIRING_PROOF = {TUTOR}

    # Por encima de esta cantidad de atletas a cargo, la pantalla avisa. NO es
    # un tope: una tutora que lleva a sus tres hijas al mismo evento es un caso
    # normal, y bloquearla no protege a nadie. El riesgo no está en la cantidad
    # sino en que el vínculo sea falso, así que esto se ve, no se impide.
    SOFT_ATHLETE_LIMIT = 4

    relation = models.CharField(
        max_length=50,
        choices=RELATION_CHOICES,
        default=ACOMP,
    )

    legal_document = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Documento de respaldo",
        help_text=(
            "Referencia del documento que acredita la tutela legal "
            "(número de acta, expediente, oficio)."
        ),
    )
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="Verificado por",
    )
    verified_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Tutor/Acompañante: {self.user}"

    @property
    def requires_proof(self):
        """¿Este vínculo necesita respaldo documental?"""
        return self.relation in self.RELATIONS_REQUIRING_PROOF

    @property
    def is_verified(self):
        return self.verified_at is not None

    @property
    def proof_pending(self):
        """Declara tutela legal pero nadie la ha verificado todavía."""
        return self.requires_proof and not self.is_verified

    @property
    def athlete_count(self):
        from accounts.models import AthleteProfile

        return AthleteProfile.objects.filter(guardian=self.user).count()

    @property
    def over_soft_limit(self):
        return self.athlete_count > self.SOFT_ATHLETE_LIMIT

    class Meta:
        verbose_name = "Perfil de Guardian"
        verbose_name_plural = "Perfiles de Guardian"


class Guardianship(models.Model):
    """Vínculo acreditado entre un atleta menor y un tutor.

    Vive en el par, no en el usuario: la misma persona puede ser madre de una
    atleta y tutora legal de otra, y cada vínculo se verifica por su cuenta.
    Un atleta puede tener N tutores, todos con los mismos permisos: no hay
    tutor "principal".
    """

    athlete = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="guardianships",
        verbose_name="Atleta",
    )
    guardian = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="guardianships_held",
        verbose_name="Tutor",
    )

    PADRE = "PADRE"
    TUTOR = "TUTOR"
    ACOMP = "ACOMP"

    RELATION_CHOICES = [
        (PADRE, "Padre / Madre"),
        (TUTOR, "Tutor legal"),
        (ACOMP, "Acompañante"),
    ]

    # Solo la tutela legal pide respaldo. `PADRE` y `ACOMP` son declarativos y
    # cubren la enorme mayoría de los casos; `TUTOR` es el que sostiene
    # decisiones sobre un menor cuando los padres no están, y ese sí no debería
    # quedar en la palabra de quien llena el formulario.
    RELATIONS_REQUIRING_PROOF = {TUTOR}

    # Por encima de esta cantidad de atletas a cargo, la pantalla avisa. NO es
    # un tope: una tutora que lleva a sus tres hijas al mismo evento es un caso
    # normal, y bloquearla no protege a nadie. El riesgo no está en la cantidad
    # sino en que el vínculo sea falso, así que esto se ve, no se impide.
    SOFT_ATHLETE_LIMIT = 4

    relation = models.CharField(
        max_length=50,
        choices=RELATION_CHOICES,
        default=ACOMP,
        verbose_name="Relación",
    )
    legal_document = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Documento de respaldo",
        help_text=(
            "Referencia del documento que acredita la tutela legal "
            "(número de acta, expediente, oficio)."
        ),
    )
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="guardianships_verified",
        verbose_name="Verificado por",
    )
    verified_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="guardianships_created",
        verbose_name="Acreditado por",
    )

    class Meta:
        verbose_name = "Vínculo de tutela"
        verbose_name_plural = "Vínculos de tutela"
        unique_together = ("athlete", "guardian")
        ordering = ["created_at", "pk"]

    def __str__(self):
        return f"{self.guardian} → {self.athlete} ({self.get_relation_display()})"

    @property
    def requires_proof(self):
        """¿Este vínculo necesita respaldo documental?"""
        return self.relation in self.RELATIONS_REQUIRING_PROOF

    @property
    def is_verified(self):
        return self.verified_at is not None

    @property
    def proof_pending(self):
        """Declara tutela legal pero nadie la ha verificado todavía."""
        return self.requires_proof and not self.is_verified

    @classmethod
    def athlete_count_for(cls, guardian) -> int:
        """Cuántos atletas tiene a cargo este tutor."""
        return cls.objects.filter(guardian=guardian).count()

    @property
    def over_soft_limit(self):
        return self.athlete_count_for(self.guardian) > self.SOFT_ATHLETE_LIMIT
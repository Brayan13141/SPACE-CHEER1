from django.db import models
from django.conf import settings


# -------------------------
# Campos de medida configurables por admin
# -------------------------
class MeasurementField(models.Model):
    FIELD_TYPE_CHOICES = [
        ("integer", "Entero"),
        ("decimal", "Decimal"),
        ("text", "Texto"),
    ]

    name = models.CharField(max_length=60)  # e.g. "Pecho", "Largo de pierna"
    slug = models.SlugField(
        max_length=80,
        unique=True,
        help_text="Slug identificador (ej: pecho, largo_pierna)",
    )
    is_active = models.BooleanField(default=True)
    field_type = models.CharField(
        max_length=10, choices=FIELD_TYPE_CHOICES, default="decimal"
    )
    unit = models.CharField(max_length=20, blank=True, help_text="unidad (ej: cm)")
    required = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]

    def __str__(self):
        return f"{self.name} ({self.unit})" if self.unit else self.name


class MeasurementValue(models.Model):
    """
    Valor concreto por usuario y campo de medida.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="measurements"
    )
    field = models.ForeignKey(
        MeasurementField, on_delete=models.CASCADE, related_name="values"
    )
    # Guardamos como texto para soportar integer/decimal/text y validarlo en forms
    value = models.CharField(max_length=50)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "field")
        ordering = ["field__order"]

    def __str__(self):
        return f"{self.user.username} - {self.field.slug}: {self.value}"


class AthleteStandardSize(models.Model):
    """Talla estándar del alumno. Es un dato del ALUMNO, no del pedido.

    Modelo aparte y no un campo en User por dos razones: updated_at/updated_by
    son lo que hace auditable el dato, y con OneToOne "sin talla capturada" es
    ausencia de fila, no un "" que se confunde con "capturada vacía".
    """

    SIZE_CHOICES = [
        ("XS", "XS"),
        ("S", "S"),
        ("M", "M"),
        ("L", "L"),
        ("XL", "XL"),
        ("XXL", "XXL"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="standard_size",
    )
    size = models.CharField(max_length=10, choices=SIZE_CHOICES)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    def __str__(self):
        return f"{self.user.username}: {self.size}"

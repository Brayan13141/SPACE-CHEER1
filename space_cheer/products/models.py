# models.py - Modelos de la aplicación products
# Contiene las definiciones de temporadas, productos, campos de medida asociados y variantes de talla.

from decimal import Decimal
from django.db import models
from django.core.exceptions import ValidationError
from measures.models import MeasurementField
from teams.models import Team
from django.core.validators import MinValueValidator


class Season(models.Model):
    """
    Representa una temporada o colección.
    Permite agrupar productos y activar/desactivar temporadas completas.
    """

    name = models.CharField(max_length=20)  # Nombre de la temporada (ej. "Otoño 2025")
    is_active = models.BooleanField(default=True)  # Indica si la temporada está vigente

    def __str__(self):
        return self.name


class Product(models.Model):
    """
    Modelo principal que representa un producto ofrecido.
    Contiene configuración de tipo, uso, alcance, estrategia de tallas,
    así como reglas de negocio y validaciones específicas.
    """

    # Tipos de producto (categoría general)
    PRODUCT_TYPE_CHOICES = [
        ("UNIFORM", "Uniforme"),
        ("SHOES", "Tenis"),
        ("BAG", "Mochila"),
        ("OTHER", "Otro"),
    ]

    # Tipo de uso: cómo se personaliza el producto
    USAGE_TYPE_CHOICES = [
        ("GLOBAL", "Global"),  # Producto estándar, sin personalización
        (
            "TEAM_CUSTOM",
            "Personalizado por equipo",
        ),  # Se puede personalizar a nivel de equipo (ej. logo)
        (
            "ATHLETE_CUSTOM",
            "Personalizado por atleta",
        ),  # Personalización individual (ej. nombre, número)
    ]

    # Estrategia de tallas: cómo se maneja el tamaño
    SIZE_STRATEGY_CHOICES = [
        ("NONE", "No usa tallas"),  # Producto sin talla (ej. accesorio)
        ("STANDARD", "Tallas estándar"),  # Tallas predefinidas (S, M, L, etc.)
        (
            "MEASUREMENTS",
            "Medidas personalizadas",
        ),  # Se toman medidas específicas del atleta
    ]

    # Alcance: ¿el producto es de catálogo general o exclusivo de un equipo?
    SCOPE_CHOICES = [
        ("CATALOG", "Catálogo"),
        ("TEAM_ONLY", "Solo un equipo"),
    ]

    # Campos básicos
    name = models.CharField(max_length=150)  # Nombre del producto
    description = models.TextField(blank=True)  # Descripción detallada

    # Clasificaciones
    product_type = models.CharField(max_length=20, choices=PRODUCT_TYPE_CHOICES)
    usage_type = models.CharField(max_length=20, choices=USAGE_TYPE_CHOICES)
    scope = models.CharField(max_length=20, choices=SCOPE_CHOICES, default="CATALOG")
    size_strategy = models.CharField(
        max_length=20, choices=SIZE_STRATEGY_CHOICES, default="NONE"
    )
    is_configured = models.BooleanField(default=False)
    # Relación con equipo (solo aplica si scope = TEAM_ONLY)
    owner_team = models.ForeignKey(
        Team,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="exclusive_products",
        help_text="Equipo dueño si el producto es exclusivo",
    )

    # Multimedia y metadata
    image = models.ImageField(upload_to="products/images/", blank=True, null=True)
    season = models.ForeignKey(
        Season, on_delete=models.PROTECT
    )  # Temporada a la que pertenece

    # Precio y estado
    base_price = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(
        default=True
    )  # Para activar/desactivar sin eliminar
    created_at = models.DateTimeField(auto_now_add=True)  # Fecha de creación

    class Meta:
        indexes = [
            models.Index(fields=["usage_type"]),
            models.Index(fields=["scope"]),
            models.Index(fields=["size_strategy"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        # Representación legible con información clave
        parts = [
            self.name,
            self.get_product_type_display(),
            self.get_usage_type_display(),
            self.get_scope_display(),
        ]
        if self.owner_team:
            parts.append(self.owner_team.name)
        return " - ".join(parts)

    def save(self, *args, **kwargs):
        """
        Guarda el producto después de ejecutar las validaciones completas.
        Se llama a full_clean() para asegurar que se ejecuten clean() y las validaciones de campo.
        """
        if self.usage_type == "GLOBAL" and self.size_strategy == "NONE":
            self.is_configured = True

        self.full_clean()  # Dispara clean() y validaciones de campo
        super().save(*args, **kwargs)

    @property
    def requires_design(self):
        """
        Determina si el producto requiere diseño gráfico.
        """
        return self.usage_type in ["TEAM_CUSTOM", "ATHLETE_CUSTOM"]

    @property
    def requires_measurements(self):
        """
        Indica si el producto requiere la captura de medidas personalizadas.
        Útil en vistas y templates para decidir si mostrar campos de medida.
        """
        return self.size_strategy == "MEASUREMENTS"

    @property
    def requires_athletes(self):
        return (
            self.usage_type in ["TEAM_CUSTOM", "ATHLETE_CUSTOM"]
            and self.size_strategy == "MEASUREMENTS"
        )

    @property
    def requires_sizes(self):
        return self.size_strategy == "STANDARD"

    @property
    def requires_team(self):
        return self.scope == "TEAM_ONLY" or self.usage_type == "TEAM_CUSTOM"

    @property
    def is_simple(self):
        return self.usage_type == "GLOBAL" and self.size_strategy == "NONE"

    # ==========================
    # VALIDATION ENTRY POINT
    # ==========================
    def clean(self):
        """
        Punto de entrada para todas las validaciones personalizadas del modelo.
        Se llama automáticamente al ejecutar full_clean() (por ejemplo, en save()).
        """
        self._validate_creation_rules()
        self._validate_size_configuration()
        self._validate_business_rules()
        self._validate_post_usage_rules()

    # ==========================
    # VALIDATIONS (métodos auxiliares)
    # ==========================

    def _validate_creation_rules(self):
        """Reglas aplicables solo al crear el producto (no al modificar)."""
        if not self.pk and not self.season.is_active:
            raise ValidationError(
                "No se pueden crear productos en temporadas inactivas"
            )

    def _validate_size_configuration(self):

        if (
            self.usage_type in ["TEAM_CUSTOM", "ATHLETE_CUSTOM"]
            and self.size_strategy == "NONE"
        ):
            raise ValidationError("Productos personalizados deben usar talla o medidas")

        if not self.pk:
            return

        original = type(self).objects.only("size_strategy").get(pk=self.pk)

        # Solo validar si se cambió la estrategia
        if original.size_strategy != self.size_strategy:

            if self.size_strategy == "STANDARD":

                if not self.size_variants.exists():
                    raise ValidationError(
                        "Producto STANDARD debe tener al menos una talla configurada"
                    )

            if self.size_strategy == "MEASUREMENTS":

                if not self.measurement_fields.exists():
                    raise ValidationError(
                        "Producto con medidas debe tener al menos un campo configurado"
                    )

    def _validate_business_rules(self):
        """
        Valida reglas de negocio entre tipo de uso, alcance,
        estrategia de tallas y equipo propietario.
        """

        errors = {}

        # GLOBAL no puede ser exclusivo de equipo
        if self.usage_type == "GLOBAL" and self.scope == "TEAM_ONLY":
            errors["Alcance"] = (
                "Un producto de uso global no puede ser exclusivo de un equipo."
            )

        # GLOBAL no puede usar medidas
        if self.usage_type == "GLOBAL" and self.size_strategy == "MEASUREMENTS":
            errors["Estrategia de talla"] = (
                "Los productos de uso global no pueden usar medidas personalizadas."
            )

        # TEAM_ONLY requiere equipo propietario
        if self.scope == "TEAM_ONLY" and not self.owner_team:
            errors["owner_team"] = (
                "Debes seleccionar el equipo dueño para productos exclusivos."
            )

        # CATALOG no debe tener equipo
        if self.scope == "CATALOG" and self.owner_team:
            errors["owner_team"] = (
                "Los productos de catálogo no deben estar asignados a un equipo."
            )

        # ATHLETE_CUSTOM requiere medidas
        if self.usage_type == "ATHLETE_CUSTOM" and self.size_strategy != "MEASUREMENTS":
            errors["Estrategia de talla"] = (
                "Los productos personalizados por atleta requieren medidas personalizadas."
            )

        if errors:
            raise ValidationError(errors)

    def _validate_post_usage_rules(self):

        if not self.pk:
            return

        original = self.__class__.objects.only(
            "scope",
            "owner_team_id",
            "size_strategy",
            "usage_type",
        ).get(pk=self.pk)

        # si nunca se ha usado en órdenes, permitir cambios
        if not self.orderitem_set.exists():
            return

        immutable_fields = [
            "scope",
            "owner_team_id",
            "size_strategy",
            "usage_type",
        ]

        for field in immutable_fields:
            if getattr(original, field) != getattr(self, field):
                raise ValidationError(
                    f"No puedes cambiar '{field}' después de que el producto fue usado en una orden"
                )

    def update_configuration_status(self):
        """
        Marca el producto como configurado cuando tiene
        las relaciones necesarias según su estrategia.
        """

        if self.size_strategy == "NONE":
            self.is_configured = True

        elif self.size_strategy == "STANDARD":
            self.is_configured = self.size_variants.exists()

        elif self.size_strategy == "MEASUREMENTS":
            self.is_configured = self.measurement_fields.exists()

        self.save(update_fields=["is_configured"])


class ProductMeasurementField(models.Model):

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="measurement_fields"
    )

    field = models.ForeignKey(MeasurementField, on_delete=models.CASCADE)

    required = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["product", "field"], name="unique_product_measurement_field"
            )
        ]

    def __str__(self):
        return f"{self.product.name} - {self.field.name} ({'req' if self.required else 'opc'})"


class ProductSizeVariant(models.Model):

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="size_variants"
    )

    size = models.CharField(max_length=20)

    additional_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["product", "size"], name="unique_product_size"
            )
        ]

    def save(self, *args, **kwargs):

        if self.size:
            self.size = self.size.upper().strip()
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product.name} - {self.size}"

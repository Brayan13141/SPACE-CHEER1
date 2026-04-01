# orders/models.py
# Modelos principales para la gestión de órdenes (pedidos) en el sistema.
# Incluye órdenes, items de producto, asignación de atletas, medidas personalizadas,
# imágenes de diseño y registro de cambios.

from functools import cached_property

from django.utils import timezone
from django.db import models
from django.conf import settings
from accounts.models import User, UserAddress
from teams.models import Team
from measures.models import MeasurementField
from django.core.exceptions import ValidationError
from teams.models import UserTeamMembership
from products.models import Product
from django.db.models import Sum, Q


# models.py — dentro de OrderQuerySet


class OrderQuerySet(models.QuerySet):

    def visible_for_user(self, user):
        if not user.is_authenticated:
            return self.none()
        if user.is_superuser or user.is_staff:
            return self
        return self.filter(
            Q(created_by=user) | Q(order_type="TEAM", owner_team__coach=user)
        ).distinct()

    def with_display_data(self):
        """
        Aplica select_related y prefetch_related para renderizar
        listas de órdenes sin queries N+1.
        Úsalo en cualquier vista que muestre múltiples órdenes.
        """
        return self.select_related(
            "owner_user",
            "owner_team",
            "created_by",
        ).prefetch_related(
            "items__product",  # para requires_design, total
        )

    def update(self, **kwargs):
        if "status" in kwargs:
            raise ValidationError(
                "No se permiten actualizaciones masivas del estado. "
                "Use OrderStateService.transition()."
            )
        return super().update(**kwargs)


class Order(models.Model):
    """
    Modelo principal que representa una orden (pedido).
    Puede ser de tipo PERSONAL (para un usuario) o TEAM (para un equipo).
    Gestiona el ciclo de vida a través de estados (STATUS_CHOICES) y transiciones controladas.
    """

    # Estados posibles de la orden
    STATUS_CHOICES = [
        ("DRAFT", "Draft"),  # Borrador, editable
        ("PENDING", "Pending"),  # Pendiente de aprobación
        ("DESIGN_APPROVED", "Design approved"),  # Diseño aprobado
        ("IN_PRODUCTION", "In production"),  # En producción
        ("DELIVERED", "Delivered"),  # Entregada
        ("CANCELLED", "Cancelled"),  # Cancelada
    ]

    # Mapa de transiciones permitidas (desde -> [destinos])
    ALLOWED_TRANSITIONS = {
        "DRAFT": ["PENDING", "CANCELLED"],
        "PENDING": ["DESIGN_APPROVED", "CANCELLED", "IN_PRODUCTION"],
        "DESIGN_APPROVED": ["IN_PRODUCTION", "CANCELLED"],
        "IN_PRODUCTION": ["DELIVERED"],
        "DELIVERED": [],
        "CANCELLED": [],
    }

    # Tipos de orden
    ORDER_TYPE_CHOICES = [
        ("PERSONAL", "Personal"),
        ("TEAM", "Team"),
    ]

    # Propietario: usuario (si PERSONAL) o equipo (si TEAM)
    order_type = models.CharField(
        max_length=20,
        choices=ORDER_TYPE_CHOICES,
    )
    owner_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="orders",
    )
    created_by = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="orders_created"
    )
    owner_team = models.ForeignKey(
        Team,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="orders",
    )
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="DRAFT",
    )

    # | measurements_open | measurements_locked | Resultado            |
    # | ----------------- | ------------------- | -------------------- |
    # | True              | False               | Editable             |
    # | False             | False               | Cerrado temporal     |
    # | False             | True                | Bloqueado definitivo |

    measurements_open = models.BooleanField(default=True)
    # Si las medidas están bloqueadas, no se pueden modificar ni agregar nuevas
    measurements_locked = models.BooleanField(default=False)
    locked_at = models.DateTimeField(null=True, blank=True)
    design_approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="approved_orders",
    )
    design_approved_at = models.DateTimeField(null=True, blank=True)
    design_notes = models.TextField(blank=True)

    # Fechas y estados finales
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    closed = models.BooleanField(
        default=False
    )  # Indica si la orden está cerrada (finalizada)
    production_started_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    # Datos de cancelación
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="cancelled_orders",
    )
    cancelled_reason = models.TextField(blank=True)
    # Pagos
    freeze_payment_date = models.DateTimeField(null=True, blank=True)
    first_payment_date = models.DateTimeField(null=True, blank=True)
    final_payment_date = models.DateTimeField(null=True, blank=True)

    # Operativo
    measurements_due_date = models.DateField(null=True, blank=True)
    uniform_delivery_date = models.DateField(null=True, blank=True)
    # Manager personalizado
    objects = OrderQuerySet.as_manager()

    # ==========================================
    # Propiedades y métodos de conveniencia
    # ==========================================

    def has_contact_info(self):
        """Verifica si la orden tiene información de contacto asociada (OneToOne)."""
        return hasattr(self, "contact_info")

    @property
    def owner(self):
        """
        Devuelve el propietario de la orden, ya sea usuario (PERSONAL) o equipo (TEAM).
        Útil para templates donde se necesita mostrar el dueño de forma genérica.
        """
        return self.owner_user if self.order_type == "PERSONAL" else self.owner_team

    @property
    def total(self):
        return self.items.aggregate(total=Sum("subtotal"))["total"] or 0

    @cached_property
    def total_quantity(self):
        """Calcula la cantidad total de productos en la orden."""
        return self.items.aggregate(total=Sum("quantity"))["total"] or 0

    class Meta:
        # Permisos personalizados para el modelo
        permissions = [
            ("can_create_order", "Can create order"),
            ("can_manage_orders", "Can manage all orders"),
        ]
        # Índices para mejorar rendimiento en búsquedas frecuentes
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["order_type"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["created_by"]),
            models.Index(fields=["owner_user"]),
            models.Index(fields=["owner_team"]),
        ]
        # Restricción a nivel BD: garantiza que owner_user y owner_team sean consistentes con order_type
        constraints = [
            models.CheckConstraint(
                condition=(
                    (
                        Q(order_type="PERSONAL")
                        & Q(owner_user__isnull=False)
                        & Q(owner_team__isnull=True)
                    )
                    | (
                        Q(order_type="TEAM")
                        & Q(owner_team__isnull=False)
                        & Q(owner_user__isnull=True)
                    )
                ),
                name="valid_owner_by_type",
            )
        ]

    def __str__(self):
        return f"Orden #{self.pk}"

    # ==========================================
    # Validaciones personalizadas (llamadas por full_clean)
    # ==========================================

    def clean(self):
        """Punto de entrada para todas las validaciones del modelo Order."""
        self._validate_owner()
        self._validate_status_rules()
        self._validate_immutability()

    @staticmethod
    def validate_order_ready(order):
        if not order.has_contact_info():
            raise ValidationError("La orden no tiene información de contacto")

        team_athletes = set()

        if order.order_type == "TEAM":
            team_athletes = set(
                UserTeamMembership.objects.filter(
                    team=order.owner_team,
                    status="accepted",
                    is_active=True,
                    role_in_team="ATLETA",
                ).values_list("user_id", flat=True)
            )
        if not order.items.exists():
            raise ValidationError("La orden debe tener al menos un item")

        for item in order.items.select_related("product").prefetch_related(
            "athletes__athlete",
            "athletes__measurements",
        ):

            if item.configuration_state != "READY":
                raise ValidationError(
                    f"El producto '{item.product.name}' no está completamente configurado"
                )

            if not item.product.requires_athletes:
                continue

            athlete_items = item.athletes.all()

            if not athlete_items.exists():
                raise ValidationError(
                    f"El producto '{item.product.name}' requiere atletas asignados"
                )

            item_athletes = set(a.athlete_id for a in athlete_items)

            if order.order_type == "TEAM":

                if item_athletes != team_athletes:

                    missing = team_athletes - item_athletes
                    extra = item_athletes - team_athletes

                    if missing:
                        raise ValidationError(
                            f"Faltan atletas del equipo en el producto '{item.product.name}'"
                        )

                    if extra:
                        raise ValidationError(
                            f"Hay atletas asignados al producto '{item.product.name}' que no pertenecen al equipo"
                        )

            for athlete_item in athlete_items:

                if item.product.requires_measurements:
                    if not athlete_item.has_complete_measurements():
                        raise ValidationError(
                            f"El atleta '{athlete_item.athlete}' no tiene todas las medidas registradas"
                        )

    def _validate_owner(self):
        """Valida que la configuración de propietario sea correcta según el tipo de orden."""
        if self.order_type == "PERSONAL":
            if not self.owner_user or self.owner_team:
                raise ValidationError("Configuración inválida para orden PERSONAL")
        elif self.order_type == "TEAM":
            if not self.owner_team or self.owner_user:
                raise ValidationError("Configuración inválida para orden TEAM")
        else:
            raise ValidationError("Tipo de orden inválido")

    def _validate_status_rules(self):
        """Reglas de estado básicas: cerrada debe estar en estados finales, orden nueva debe ser DRAFT."""
        if self.closed and self.status not in ["DELIVERED", "CANCELLED"]:
            raise ValidationError("Una orden cerrada debe estar DELIVERED o CANCELLED")

        if not self.pk and self.status != "DRAFT":
            raise ValidationError("Las órdenes nuevas deben comenzar en DRAFT")

    def _validate_immutability(self):
        """
        Valida que ciertos campos no puedan cambiar después de creada la orden.
        Por ejemplo, el tipo de orden (PERSONAL/TEAM) es inmutable.
        """
        if not self.pk:
            return

        original_type = (
            type(self)
            .objects.filter(pk=self.pk)
            .values_list("order_type", flat=True)
            .first()
        )

        if original_type and original_type != self.order_type:
            raise ValidationError("El tipo de orden no puede cambiarse una vez creada")

    def can_edit_general(self):
        return (
            self.status in ["DRAFT", "PENDING", "DESIGN_APPROVED"] and not self.closed
        )

    def can_edit_measurements(self):
        if self.measurements_locked:
            return False

        if not self.measurements_open:
            return False

        if not self.can_edit_general():
            return False

        return True

    def can_edit_items(self):
        """La orden permite agregar/eliminar items."""
        return self.status == "DRAFT" and not self.closed

    @cached_property
    def requires_design(self):
        return any(item.product.requires_design for item in self.items.all())

    def invalidate_cache(self):
        for attr in ("total_quantity", "requires_design"):
            self.__dict__.pop(attr, None)

    def _validate_operational_dates(self):
        """
        Si ambas fechas existen, la entrega no puede ser
        anterior a la fecha límite de medidas.
        """
        if self.measurements_due_date and self.uniform_delivery_date:
            if self.uniform_delivery_date < self.measurements_due_date:
                raise ValidationError(
                    "La fecha de entrega del uniforme no puede ser anterior "
                    "a la fecha límite de entrega de medidas."
                )

    # ==========================================
    # Sobrescritura de save
    # ==========================================

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")

        if self.pk and not update_fields:  # Solo en saves completos
            original = (
                type(self)
                .objects.only("status", "owner_user_id", "owner_team_id")
                .get(pk=self.pk)
            )
            if original.owner_user_id != self.owner_user_id:
                raise ValidationError("No se puede cambiar el propietario de la orden.")
            if original.owner_team_id != self.owner_team_id:
                raise ValidationError("No se puede cambiar el equipo de la orden.")
            if not getattr(self, "_allow_status_change", False):
                if original.status != self.status:
                    raise ValidationError(
                        "No se permite modificar el estado directamente."
                    )

        if not update_fields:
            self.full_clean()
        super().save(*args, **kwargs)

        if hasattr(self, "_allow_status_change"):
            del self._allow_status_change


class OrderContactInfo(models.Model):
    """
    Información de contacto y dirección de envío asociada a una orden.
    Relación uno a uno con Order.
    """

    order = models.OneToOneField(
        "orders.Order",
        on_delete=models.CASCADE,
        related_name="contact_info",
    )

    # Datos de contacto
    contact_name = models.CharField(max_length=150)
    contact_phone = models.CharField(max_length=20, blank=True)
    contact_email = models.EmailField()

    # Dirección de envío
    shipping_address_line = models.CharField(max_length=255, blank=True)
    shipping_city = models.CharField(max_length=100, blank=True)
    shipping_postal_code = models.CharField(max_length=20, blank=True)
    shipping_notes = models.TextField(blank=True)

    # Metadatos
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    closed = models.BooleanField(
        default=False
    )  # Si está cerrada, no se puede modificar

    def clean(self):

        missing = []

        if not self.contact_name:
            missing.append("Nombre")

        if not self.contact_phone:
            missing.append("Teléfono")

        if not self.contact_email:
            missing.append("Email")

        if not self.shipping_address_line:
            missing.append("Dirección")

        if not self.shipping_city:
            missing.append("Ciudad")

        if not self.shipping_postal_code:
            missing.append("Código postal")

        if missing:
            raise ValidationError(
                f"Faltan campos obligatorios: {', '.join(missing)} debes completar tu informacion de contacto"
            )

    def __str__(self):
        return f"Contacto envío - Orden #{self.order_id}"

    def save(self, *args, **kwargs):
        """
        Solo permite guardar/modificar la información de contacto si la orden es editable.
        """
        if self.pk:  # Solo para objetos existentes, no al crear
            original = (
                OrderContactInfo.objects.filter(pk=self.pk)
                .values_list("closed", flat=True)
                .first()
            )
            if original:  # Si ya estaba cerrada en DB
                raise ValidationError(
                    "La información de contacto está cerrada y no puede modificarse."
                )

        super().save(*args, **kwargs)


class OrderItem(models.Model):
    """
    Representa un producto (item) dentro de una orden.
    Incluye cantidad, precio unitario, subtotal y la variante de talla seleccionada (si aplica).
    """

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT)

    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)

    size_variant = models.ForeignKey(
        "products.ProductSizeVariant", null=True, blank=True, on_delete=models.PROTECT
    )

    class Meta:
        # Índices para mejorar rendimiento en búsquedas frecuentes
        indexes = [
            models.Index(fields=["order"]),
            models.Index(fields=["product"]),
        ]

    def calculate_unit_price(self):
        """Calcula el precio unitario (base + adicional de talla)."""
        price = self.product.base_price
        if self.size_variant:
            price += self.size_variant.additional_price
        return price

    def save(self, *args, **kwargs):
        """
        Guarda el item después de recalcular precios y validar editabilidad.
        No permite cambiar la talla después de creado el item.
        """
        if not self.order.can_edit_general():
            raise ValidationError(
                "Los items no pueden modificarse después de la aprobación del diseño"
            )

        if self.pk:
            original_variant = (
                type(self)
                .objects.filter(pk=self.pk)
                .values_list("size_variant_id", flat=True)
                .first()
            )
            if original_variant != self.size_variant_id:
                raise ValidationError(
                    "No se puede cambiar la talla después de crear el item"
                )

        # Recalcular precios siempre antes de guardar
        self.unit_price = self.calculate_unit_price()
        self.subtotal = self.unit_price * self.quantity

        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Evita eliminar items si la orden no es editable."""
        if not self.order.can_edit_general():
            raise ValidationError(
                "Los items no pueden ser eliminados después de aprobar el diseño"
            )
        super().delete(*args, **kwargs)

    def clean(self):
        """Validaciones de negocio para el item."""
        self._validate_editable()
        self._validate_quantity()
        self._validate_size()
        self._validate_scope_rules()
        self._validate_athlete_rules()

    @property
    def needs_athletes(self):
        return self.product.requires_athletes

    @property
    def needs_size(self):
        return self.product.requires_sizes

    @property
    def missing_configuration(self):

        missing = []

        if self.needs_size and not self.size_variant:
            missing.append("Seleccionar talla")

        if self.needs_athletes and not self.athletes.exists():
            missing.append("Asignar atletas")

        if self.product.requires_measurements:
            athletes = self.athletes.prefetch_related("measurements")
            for athlete in athletes:
                if not athlete.has_complete_measurements():
                    missing.append(f"Medidas de {athlete.athlete}")
                    break

        return missing

    @property
    def configuration_state(self):

        if self.needs_size and not self.size_variant:
            return "INCOMPLETE"

        if self.needs_athletes and not self.athletes.exists():
            return "INCOMPLETE"

        if self.product.requires_measurements:

            for athlete in self.athletes.prefetch_related("measurements"):
                if not athlete.has_complete_measurements():
                    return "INCOMPLETE"

        return "READY"

    def _validate_editable(self):
        if not self.order.can_edit_general():
            raise ValidationError("La orden no es editable")

    def _validate_quantity(self):
        if self.quantity <= 0:
            raise ValidationError("La cantidad debe ser mayor a cero")

    def _validate_size(self):
        """Valida la consistencia entre la estrategia de talla del producto y la variante seleccionada."""
        product = self.product

        if product.size_strategy == "STANDARD" and not self.size_variant:
            raise ValidationError("Se requiere seleccionar una talla")

        if product.size_strategy != "STANDARD" and self.size_variant:
            raise ValidationError("Este producto no usa tallas estándar")

        if self.size_variant and self.size_variant.product_id != product.id:
            raise ValidationError("La talla no pertenece a este producto")

    def _validate_scope_rules(self):
        """Valida reglas de alcance: productos TEAM_ONLY solo en órdenes de equipo y con el equipo correcto."""
        product = self.product
        order = self.order

        if product.scope == "TEAM_ONLY":
            if order.order_type != "TEAM":
                raise ValidationError(
                    "Producto exclusivo de equipo requiere una orden TEAM"
                )
            if product.owner_team_id != order.owner_team_id:
                raise ValidationError("El producto no pertenece a este equipo")

    def _validate_athlete_rules(self):
        """
        Valida reglas relacionadas con la asignación de atletas.
        Si el producto es ATHLETE_CUSTOM, la orden debe ser TEAM y la cantidad debe coincidir con atletas asignados.
        """
        product = self.product
        order = self.order

        if product.usage_type == "ATHLETE_CUSTOM":
            if order.order_type != "TEAM":
                raise ValidationError("ATHLETE_CUSTOM solo se permite en órdenes TEAM")

            # Si el item ya está guardado, validamos que la cantidad coincida con el número de atletas asignados
            if self.pk and self.athletes.count() != self.quantity:
                raise ValidationError(
                    "La cantidad debe coincidir con el número de atletas asignados"
                )


class OrderItemAthlete(models.Model):
    """
    Asocia un atleta (usuario) a un item de orden.
    Se usa cuando el producto requiere personalización por atleta (ATHLETE_CUSTOM).
    También puede usarse para llevar control de a quién pertenece cada unidad en productos con talla estándar
    si se desea asignar, pero las validaciones actuales lo restringen.
    """

    order_item = models.ForeignKey(
        OrderItem, on_delete=models.CASCADE, related_name="athletes"
    )
    athlete = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="uniform_orders"
    )

    def clean(self):
        """
        Validaciones:
        - El producto no debe ser GLOBAL.
        - La estrategia de talla no debe ser STANDARD ni NONE.
        - El atleta debe pertenecer al equipo (si orden TEAM) o ser el propio usuario (si PERSONAL).
        """
        order = self.order_item.order
        product = self.order_item.product

        if product.usage_type == "GLOBAL":
            raise ValidationError("Producto GLOBAL no usa asignación por atleta")

        if not product.requires_athletes:
            raise ValidationError("Este producto no permite asignación por atleta")

        if order.order_type == "TEAM":
            # Verificar que el atleta sea miembro activo del equipo
            if not UserTeamMembership.objects.filter(
                user=self.athlete,
                team=order.owner_team,
                status="accepted",
                is_active=True,
                role_in_team="ATLETA",
            ).exists():
                raise ValidationError("El usuario no es atleta activo del equipo")
        else:
            # Orden personal: el único atleta posible es el propietario
            if self.athlete != order.owner_user:
                raise ValidationError("Orden personal: atleta inválido")

    def has_complete_measurements(self):
        required_fields = list(
            self.order_item.product.measurement_fields.filter(
                required=True
            ).values_list("field_id", flat=True)
        )

        if not required_fields:
            return True

        # Con CharField: un valor es válido si existe y no está vacío
        existing_with_values = (
            self.measurements.filter(
                field_id__in=required_fields,
            )
            .exclude(value="")  # excluir medidas vacías
            .values_list("field_id", flat=True)
        )

        return set(required_fields) == set(existing_with_values)

    def save(self, *args, **kwargs):
        """Ejecuta validaciones y verifica que la orden sea editable."""
        self.full_clean()
        if not self.order_item.order.can_edit_general():
            raise ValidationError("Los items no pueden modificarse en esta etapa.")
        super().save(*args, **kwargs)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["order_item", "athlete"], name="unique_athlete_per_order_item"
            )
        ]
        indexes = [
            models.Index(fields=["order_item"]),
            models.Index(fields=["athlete"]),
        ]


class OrderItemMeasurement(models.Model):
    """
    Snapshot híbrido de medidas por atleta dentro de un item.

    value_original: string copiado del perfil del atleta al importar
    value: editable dentro de la orden (inicia igual a value_original)
    is_modified: True si el coach editó manualmente el valor de la orden

    "" (vacío) = el atleta no tenía esta medida al momento del snapshot
    valor != "" = medida registrada
    """

    athlete_item = models.ForeignKey(
        "OrderItemAthlete",
        on_delete=models.CASCADE,
        related_name="measurements",
    )
    field = models.ForeignKey("measures.MeasurementField", on_delete=models.PROTECT)

    field_name = models.CharField(max_length=100)
    field_unit = models.CharField(max_length=20, blank=True)

    # CharField para ser fiel a MeasurementValue.value
    # Soporta integer, decimal y text sin conversión
    value_original = models.CharField(max_length=50, blank=True, default="")
    value = models.CharField(max_length=50, blank=True, default="")

    is_modified = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["athlete_item", "field"],
                name="unique_measurement_per_field_per_athlete",
            )
        ]
        indexes = [
            models.Index(fields=["athlete_item"]),
            models.Index(fields=["field"]),
        ]

    @property
    def has_value(self) -> bool:
        """True si el atleta tiene esta medida registrada."""
        return bool(self.value and self.value.strip())

    @property
    def display_value(self) -> str:
        """
        Para templates: nunca muestra None ni string vacío.
        Muestra el valor con unidad o un placeholder visual.
        """
        if not self.has_value:
            return "—"  # guión largo, no "None"
        unit = f" {self.field_unit}" if self.field_unit else ""
        return f"{self.value}{unit}"

    def clean(self):
        order = self.athlete_item.order_item.order

        if not order.can_edit_measurements():
            raise ValidationError("Las medidas no pueden editarse")

        product = self.athlete_item.order_item.product

        if product.size_strategy != "MEASUREMENTS":
            raise ValidationError("Este producto no usa medidas")

        if not product.measurement_fields.filter(field=self.field).exists():
            raise ValidationError("Campo no pertenece al producto")

    def save(self, *args, **kwargs):
        if not self.field_name:
            self.field_name = self.field.name
            self.field_unit = self.field.unit

        # Detectar modificación: solo si el valor difiere del original
        # y el original no estaba vacío (una medida nueva no cuenta como "modificada")
        if self.value_original and self.value != self.value_original:
            self.is_modified = True

        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.athlete_item.athlete} - {self.field_name}: {self.display_value}"


class OrderDesignImage(models.Model):
    """
    Imágenes de diseño asociadas a una orden (ej. mockups, arte).
    Permite marcar una imagen como final (is_final), con restricción de una única final por orden.
    """

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="design_images",
    )
    image = models.ImageField(upload_to="orders/designs/")
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
    )
    is_final = models.BooleanField(
        default=False
    )  # Indica si esta imagen es la versión final aprobada
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["order"],
                condition=Q(is_final=True),
                name="unique_final_design_per_order",
            )
        ]


class OrderItemCustomization(models.Model):
    """
    Personalización adicional para un atleta en un producto (por ejemplo, texto personalizado).
    Relación uno a uno con OrderItemAthlete.
    """

    athlete_item = models.OneToOneField(
        OrderItemAthlete,
        on_delete=models.CASCADE,
        related_name="customization",
    )

    custom_text = models.CharField(max_length=50)

    def clean(self):
        """
        Validaciones: solo permitido en productos con estrategia MEASUREMENTS y uso ATHLETE_CUSTOM.
        """
        product = self.athlete_item.order_item.product
        if product.size_strategy != "MEASUREMENTS":
            raise ValidationError(
                "Personalización solo permitida en productos por medida"
            )

        if product.usage_type != "ATHLETE_CUSTOM":
            raise ValidationError("Este producto no admite personalización")

    def save(self, *args, **kwargs):
        """Solo se puede guardar si la orden es editable."""
        order = self.athlete_item.order_item.order

        if not order.can_edit_general():
            raise ValidationError(
                "La personalización no puede modificarse después de la aprobación del diseño."
            )

        self.full_clean()
        super().save(*args, **kwargs)


class OrderLog(models.Model):
    """
    Registro de auditoría para cambios de estado y acciones relevantes en la orden.
    Guarda quién hizo el cambio, estado anterior y nuevo, notas y metadatos adicionales en JSON.
    """

    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(
        max_length=100
    )  # Descripción de la acción (ej. "status_change", "note_added")
    from_status = models.CharField(max_length=30)  # Estado anterior
    to_status = models.CharField(max_length=30)  # Nuevo estado
    notes = models.TextField(blank=True)
    metadata = models.JSONField(
        default=dict,
        blank=True,  # Almacena datos adicionales (ej. ID de aprobación, razones)
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["order", "created_at"]),
            models.Index(fields=["user", "created_at"]),
        ]

    def __str__(self):
        return f"Orden #{self.order_id}: {self.from_status} → {self.to_status}"

from django.db import models
from django.conf import settings


class ProductionTemplate(models.Model):
    """Grupo reutilizable de etapas de producción para aplicar a productos."""
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    stages = models.ManyToManyField(
        "ProductionStage",
        through="ProductionTemplateStage",
        related_name="templates",
        blank=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="production_templates_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class ProductionTemplateStage(models.Model):
    template = models.ForeignKey(
        ProductionTemplate, on_delete=models.CASCADE, related_name="template_stages"
    )
    stage = models.ForeignKey("ProductionStage", on_delete=models.CASCADE)
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        unique_together = [("template", "stage")]
        ordering = ["display_order"]

    def __str__(self):
        return f"{self.template.name} — {self.stage.name}"


class ProductionStage(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    icon = models.CharField(max_length=10, blank=True)
    display_order = models.PositiveSmallIntegerField(default=0)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["display_order"]

    def __str__(self):
        return self.name


class ProductStageConfig(models.Model):
    product = models.ForeignKey(
        "products.Product", on_delete=models.CASCADE, related_name="stage_configs"
    )
    stage = models.ForeignKey(ProductionStage, on_delete=models.CASCADE, related_name="stage_configs")
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        unique_together = [("product", "stage")]
        ordering = ["display_order"]

    def __str__(self):
        return f"{self.product} — {self.stage}"


class ProductionRole(models.Model):
    name = models.CharField(max_length=100)
    stages = models.ManyToManyField(ProductionStage, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class OperarioRoleAssignment(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="production_roles",
    )
    role = models.ForeignKey(ProductionRole, on_delete=models.CASCADE)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="production_assignments_made",
    )
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("user", "role")]

    def __str__(self):
        return f"{self.user} — {self.role}"


class ProductionJob(models.Model):
    order = models.OneToOneField(
        "orders.Order", on_delete=models.CASCADE, related_name="production_job"
    )
    is_urgent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Job #{self.pk} — Orden #{self.order_id}"


class ProductionTask(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pendiente"
        COMPLETED = "COMPLETED", "Completada"

    job = models.ForeignKey(ProductionJob, on_delete=models.CASCADE, related_name="tasks")
    order_item = models.ForeignKey(
        "orders.OrderItem", on_delete=models.CASCADE, related_name="production_tasks"
    )
    stage = models.ForeignKey(ProductionStage, on_delete=models.PROTECT)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_production_tasks",
    )
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="completed_production_tasks",
    )
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = [("job", "order_item", "stage")]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["assigned_to"]),
            models.Index(fields=["job"]),
        ]

    def __str__(self):
        return f"Task {self.stage} — {self.job}"


class StageResponsibility(models.Model):
    """Defines the primary responsible role and auxiliaries for each production stage."""
    stage = models.OneToOneField(
        ProductionStage, on_delete=models.CASCADE, related_name="responsibility"
    )
    responsible_role = models.ForeignKey(
        ProductionRole,
        on_delete=models.PROTECT,
        related_name="primary_stages",
    )
    auxiliary_roles = models.ManyToManyField(
        ProductionRole,
        blank=True,
        related_name="auxiliary_stages",
    )

    class Meta:
        verbose_name = "Responsabilidad de etapa"
        verbose_name_plural = "Responsabilidades de etapas"

    def __str__(self):
        return f"{self.stage} → Responsable: {self.responsible_role}"


class ErrorReport(models.Model):
    """Reporte de Error — documenta errores en el proceso de producción."""

    class ErrorType(models.TextChoices):
        WRONG_SIZES = "WRONG_SIZES", "Tallas incorrectas"
        WRONG_CUT = "WRONG_CUT", "Corte equivocado"
        WRONG_SUBLIMATION = "WRONG_SUBLIMATION", "Sublimación incorrecta"
        WRONG_APPLICATION = "WRONG_APPLICATION", "Aplicación / Cristalería incorrecta"
        DEFECTIVE_SEWING = "DEFECTIVE_SEWING", "Costura defectuosa"
        WRONG_MATERIAL = "WRONG_MATERIAL", "Material incorrecto"
        WRONG_QUANTITY = "WRONG_QUANTITY", "Cantidad incorrecta"
        INCOMPLETE_ORDER = "INCOMPLETE_ORDER", "Pedido incompleto"
        PROCESS_DELAY = "PROCESS_DELAY", "Retraso en proceso"
        OTHER = "OTHER", "Otro"

    class ErrorCause(models.TextChoices):
        LACK_OF_ATTENTION = "LACK_OF_ATTENTION", "Falta de atención"
        DIDNT_FOLLOW_PROCESS = "DIDNT_FOLLOW_PROCESS", "No siguió el proceso"
        WRONG_INFO = "WRONG_INFO", "Información incorrecta"
        LACK_OF_REVIEW = "LACK_OF_REVIEW", "Falta de revisión"
        LACK_OF_TRAINING = "LACK_OF_TRAINING", "Falta de capacitación"
        LACK_OF_COMMUNICATION = "LACK_OF_COMMUNICATION", "Falta de comunicación"
        RUSH = "RUSH", "Prisa / Apuro"
        OTHER = "OTHER", "Otro"

    class ErrorImpact(models.TextChoices):
        DELIVERY_DELAY = "DELIVERY_DELAY", "Retraso en entrega"
        REDO_GARMENT = "REDO_GARMENT", "Rehacer la prenda / pieza"
        WASTED_MATERIAL = "WASTED_MATERIAL", "Material desperdiciado"
        ADDITIONAL_COST = "ADDITIONAL_COST", "Costo adicional"
        UNHAPPY_CLIENT = "UNHAPPY_CLIENT", "Cliente inconforme"
        AFFECTS_QUALITY = "AFFECTS_QUALITY", "Afecta calidad del producto"
        OTHER = "OTHER", "Otro"

    class ReviewStatus(models.TextChoices):
        PENDING = "PENDING", "Pendiente de revisión"
        REVIEWED = "REVIEWED", "Revisado"
        EXCEPTION_GRANTED = "EXCEPTION_GRANTED", "Excepción otorgada"
        REPOSITION_REQUIRED = "REPOSITION_REQUIRED", "Reposición requerida"

    # ── Meta ─────────────────────────────────────────────────────────────────
    reported_at = models.DateTimeField(auto_now_add=True)
    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="error_reports_filed",
    )

    # ── Sección 1: Información general ───────────────────────────────────────
    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.CASCADE,
        related_name="error_reports",
        null=True,
        blank=True,
    )
    job = models.ForeignKey(
        ProductionJob,
        on_delete=models.SET_NULL,
        related_name="error_reports",
        null=True,
        blank=True,
    )
    stage = models.ForeignKey(
        ProductionStage,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    area = models.CharField(max_length=200, blank=True)

    # ── Sección 2: Tipo de error ─────────────────────────────────────────────
    error_types = models.JSONField(default=list)
    error_type_other = models.CharField(max_length=200, blank=True)

    # ── Sección 3: Descripción del error ─────────────────────────────────────
    description = models.TextField()

    # ── Sección 4: Responsable del error ─────────────────────────────────────
    responsible = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="error_reports_responsible",
    )
    responsible_area = models.CharField(max_length=200, blank=True)
    error_causes = models.JSONField(default=list)
    cause_other = models.CharField(max_length=200, blank=True)
    cause_detail = models.TextField(blank=True)

    # ── Sección 5: Impacto del error ─────────────────────────────────────────
    error_impacts = models.JSONField(default=list)
    impact_other = models.CharField(max_length=200, blank=True)
    impact_description = models.TextField(blank=True)

    # ── Sección 6: Acciones correctivas inmediatas ────────────────────────────
    corrective_actions = models.TextField(blank=True)

    # ── Sección 7: Acciones para evitar repetición ────────────────────────────
    prevention_actions = models.TextField(blank=True)

    # ── Revisión por Dirección ────────────────────────────────────────────────
    review_status = models.CharField(
        max_length=30,
        choices=ReviewStatus.choices,
        default=ReviewStatus.PENDING,
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="error_reports_reviewed",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)

    # ── Reposición ────────────────────────────────────────────────────────────
    requires_reposition = models.BooleanField(default=False)
    is_exception = models.BooleanField(default=False)
    exception_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["-reported_at"]
        verbose_name = "Reporte de error"
        verbose_name_plural = "Reportes de error"

    def __str__(self):
        return f"Reporte #{self.pk} — {self.get_review_status_display()}"

    def get_error_types_display(self):
        label_map = dict(self.ErrorType.choices)
        return [label_map.get(t, t) for t in self.error_types]

    def get_error_causes_display(self):
        label_map = dict(self.ErrorCause.choices)
        return [label_map.get(c, c) for c in self.error_causes]

    def get_error_impacts_display(self):
        label_map = dict(self.ErrorImpact.choices)
        return [label_map.get(i, i) for i in self.error_impacts]

    @property
    def is_reposition_type(self):
        """Returns True if any error type triggers automatic reposition consideration."""
        reposition_types = {
            self.ErrorType.WRONG_SIZES,
            self.ErrorType.WRONG_CUT,
            self.ErrorType.WRONG_SUBLIMATION,
            self.ErrorType.WRONG_APPLICATION,
            self.ErrorType.DEFECTIVE_SEWING,
            self.ErrorType.INCOMPLETE_ORDER,
        }
        return bool(set(self.error_types) & reposition_types)

from django.db import models
from django.conf import settings


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
    stage = models.ForeignKey(ProductionStage, on_delete=models.CASCADE)
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
    STATUS_CHOICES = [
        ("PENDING", "Pendiente"),
        ("COMPLETED", "Completada"),
    ]

    job = models.ForeignKey(ProductionJob, on_delete=models.CASCADE, related_name="tasks")
    order_item = models.ForeignKey(
        "orders.OrderItem", on_delete=models.CASCADE, related_name="production_tasks"
    )
    stage = models.ForeignKey(ProductionStage, on_delete=models.PROTECT)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
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
    started_at = models.DateTimeField()
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

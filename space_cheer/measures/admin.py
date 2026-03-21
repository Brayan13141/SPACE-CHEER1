# measures/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count
from django.urls import reverse

from .forms import MeasurementFieldForm
from .models import MeasurementField, MeasurementValue


def format_int(value):
    """Convierte cualquier cosa a entero seguro en string"""
    try:
        return str(int(value))
    except (ValueError, TypeError):
        return "0"


# ============================================================
# MEASUREMENT VALUE INLINE
# ============================================================
class MeasurementValueInline(admin.TabularInline):
    model = MeasurementValue
    extra = 0
    fields = ("user", "value", "updated_at")
    readonly_fields = ("updated_at",)
    raw_id_fields = ("user",)

    def get_queryset(self, request):
        return (
            super().get_queryset(request).select_related("user").order_by("-updated_at")
        )


# ============================================================
# MEASUREMENT FIELD ADMIN
# ============================================================
@admin.register(MeasurementField)
class MeasurementFieldAdmin(admin.ModelAdmin):
    form = MeasurementFieldForm
    list_display = (
        "order_display",
        "name",
        "slug",
        "field_type_badge",
        "unit_display",
        "required_badge",
        "active_badge",
        "value_count",
    )
    list_filter = (
        "is_active",
        "field_type",
        "required",
    )
    search_fields = ("name", "slug", "unit")
    ordering = ("order", "name")
    prepopulated_fields = {"slug": ("name",)}

    # Inlines
    inlines = [MeasurementValueInline]

    fieldsets = (
        (
            "Información Básica",
            {
                "fields": (
                    "name",
                    "slug",
                    "order",
                )
            },
        ),
        (
            "Configuración",
            {
                "fields": (
                    ("field_type", "unit"),
                    ("required", "is_active"),
                )
            },
        ),
    )

    # Protección del slug
    def get_readonly_fields(self, request, obj=None):
        if obj and obj.values.exists():
            # Si ya tiene valores, no permitir cambiar el slug
            return ("slug",)
        return ()

    # ============ MÉTODOS DE DISPLAY ============

    def order_display(self, obj):
        order_str = format_int(obj.order).zfill(2)

        return format_html(
            '<span style="background: #f0f0f0; padding: 2px 8px; border-radius: 3px; '
            'font-family: monospace; font-weight: bold;">{}</span>',
            order_str,
        )

    order_display.short_description = "Orden"
    order_display.admin_order_field = "order"

    def field_type_badge(self, obj):
        colors = {
            "integer": "#007bff",
            "decimal": "#28a745",
            "text": "#6c757d",
        }
        color = colors.get(obj.field_type, "#6c757d")

        return format_html(
            '<span style="background: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color,
            obj.get_field_type_display(),
        )

    field_type_badge.short_description = "Tipo"

    def unit_display(self, obj):
        if obj.unit:
            return format_html(
                '<code style="background: #f0f0f0; padding: 2px 6px; '
                'border-radius: 3px;">{}</code>',
                obj.unit,
            )
        return format_html('<span style="color: #999;">-</span>')

    unit_display.short_description = "Unidad"

    def required_badge(self, obj):
        if obj.required:
            return format_html(
                '<span style="color: #dc3545; font-weight: bold;">✓ Requerido</span>'
            )
        return format_html('<span style="color: #999;">○ Opcional</span>')

    required_badge.short_description = "Obligatorio"

    def active_badge(self, obj):
        if obj.is_active:
            return format_html('<span style="color: #28a745;">✓ Activo</span>')
        return format_html('<span style="color: #999;">✗ Inactivo</span>')

    active_badge.short_description = "Estado"

    def value_count(self, obj):
        """Número de valores registrados para este campo"""
        count = obj.values.count()

        if count == 0:
            return format_html('<span style="color: #999;">0 valores</span>')

        url = (
            reverse("admin:measures_measurementvalue_changelist")
            + f"?field__id__exact={obj.id}"
        )
        return format_html('<a href="{}">{} valores</a>', url, count)

    value_count.short_description = "Valores registrados"
    value_count.admin_order_field = "value_count_annotated"

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(value_count_annotated=Count("values", distinct=True))
        )

    # ============ ACCIONES BULK ============

    actions = ["activate_fields", "deactivate_fields", "mark_as_required"]

    @admin.action(description="✓ Activar campos seleccionados")
    def activate_fields(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} campos activados.")

    @admin.action(description="✗ Desactivar campos seleccionados")
    def deactivate_fields(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} campos desactivados.")

    @admin.action(description="📋 Marcar como requeridos")
    def mark_as_required(self, request, queryset):
        updated = queryset.update(required=True)
        self.message_user(request, f"{updated} campos marcados como requeridos.")


# ============================================================
# MEASUREMENT VALUE ADMIN
# ============================================================
@admin.register(MeasurementValue)
class MeasurementValueAdmin(admin.ModelAdmin):
    list_display = (
        "user_link",
        "field_link",
        "value_display",
        "unit_display",
        "updated_at",
    )
    list_filter = (
        "field",
        ("updated_at", admin.DateFieldListFilter),
    )
    search_fields = (
        "user__username",
        "user__email",
        "user__first_name",
        "user__last_name",
        "field__name",
        "field__slug",
        "value",
    )
    raw_id_fields = ("user", "field")
    readonly_fields = ("updated_at",)
    date_hierarchy = "updated_at"

    fieldsets = (
        ("Relación", {"fields": ("user", "field")}),
        ("Valor", {"fields": ("value", "updated_at")}),
    )

    def user_link(self, obj):
        url = reverse("admin:accounts_user_change", args=[obj.user.id])
        return format_html(
            '<a href="{}">{}</a>', url, obj.user.get_full_name() or obj.user.username
        )

    user_link.short_description = "Usuario"
    user_link.admin_order_field = "user__last_name"

    def field_link(self, obj):
        url = reverse("admin:measures_measurementfield_change", args=[obj.field.id])
        return format_html('<a href="{}">{}</a>', url, obj.field.name)

    field_link.short_description = "Campo"
    field_link.admin_order_field = "field__name"

    def value_display(self, obj):
        return format_html('<strong style="font-size: 14px;">{}</strong>', obj.value)

    value_display.short_description = "Valor"

    def unit_display(self, obj):
        if obj.field.unit:
            return format_html(
                '<code style="background: #f0f0f0; padding: 2px 6px; border-radius: 3px;">{}</code>',
                obj.field.unit,
            )
        return format_html('<span style="color: #999;">-</span>')

    unit_display.short_description = "Unidad"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user", "field")

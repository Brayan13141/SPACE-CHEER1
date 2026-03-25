from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Count, Sum, Q
from django.contrib import messages
from django.shortcuts import redirect
from django.http import HttpResponse
import csv
from datetime import datetime

from orders.models import (
    Order,
    OrderItem,
    OrderItemAthlete,
    OrderItemMeasurement,
    OrderContactInfo,
    OrderDesignImage,
    OrderLog,
)


# ============================================================
# INLINES
# ============================================================


class OrderItemInline(admin.TabularInline):
    """Items de la orden como inline"""

    model = OrderItem
    extra = 0
    fields = ("product", "quantity", "size_variant", "unit_price", "subtotal")
    readonly_fields = ("unit_price", "subtotal")

    def has_add_permission(self, request, obj=None):
        # Solo permitir agregar si la orden es DRAFT
        if obj and obj.status != "DRAFT":
            return False
        return super().has_add_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        # Solo permitir eliminar si la orden es DRAFT
        if obj and obj.status != "DRAFT":
            return False
        return super().has_delete_permission(request, obj)


class OrderContactInfoInline(admin.StackedInline):
    """Información de contacto como inline"""

    model = OrderContactInfo
    fields = (
        "contact_name",
        "contact_phone",
        "contact_email",
        "shipping_address_line",
        "shipping_city",
        "shipping_postal_code",
        "shipping_notes",
        "closed",
    )
    readonly_fields = ("closed",)

    def has_delete_permission(self, request, obj=None):
        return False  # No permitir eliminar info de contacto


class OrderDesignImageInline(admin.TabularInline):
    """Imágenes de diseño como inline"""

    model = OrderDesignImage
    extra = 0
    fields = ("image", "is_final", "uploaded_by", "created_at")
    readonly_fields = ("uploaded_by", "created_at")


class OrderLogInline(admin.TabularInline):
    """Logs de auditoría como inline"""

    model = OrderLog
    extra = 0
    fields = ("created_at", "user", "action", "from_status", "to_status", "notes")
    readonly_fields = (
        "created_at",
        "user",
        "action",
        "from_status",
        "to_status",
        "notes",
    )

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


# ============================================================
# FILTERS
# ============================================================


class OrderStatusFilter(admin.SimpleListFilter):
    """Filtro personalizado por estado"""

    title = "Estado de orden"
    parameter_name = "status"

    def lookups(self, request, model_admin):
        return Order.STATUS_CHOICES

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(status=self.value())
        return queryset


class OrderTypeFilter(admin.SimpleListFilter):
    """Filtro por tipo de orden"""

    title = "Tipo de orden"
    parameter_name = "type"

    def lookups(self, request, model_admin):
        return Order.ORDER_TYPE_CHOICES

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(order_type=self.value())
        return queryset


class MeasurementsStatusFilter(admin.SimpleListFilter):
    """Filtro por estado de medidas"""

    title = "Estado de medidas"
    parameter_name = "measurements"

    def lookups(self, request, model_admin):
        return (
            ("open", "Abiertas"),
            ("closed", "Cerradas (temporal)"),
            ("locked", "Bloqueadas (definitivo)"),
        )

    def queryset(self, request, queryset):
        if self.value() == "open":
            return queryset.filter(measurements_open=True, measurements_locked=False)
        elif self.value() == "closed":
            return queryset.filter(measurements_open=False, measurements_locked=False)
        elif self.value() == "locked":
            return queryset.filter(measurements_locked=True)
        return queryset


class HasDesignFilter(admin.SimpleListFilter):
    """Filtro por si tiene diseño final"""

    title = "Diseño final"
    parameter_name = "design"

    def lookups(self, request, model_admin):
        return (
            ("yes", "Con diseño final"),
            ("no", "Sin diseño final"),
        )

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.filter(design_images__is_final=True).distinct()
        elif self.value() == "no":
            return queryset.exclude(design_images__is_final=True).distinct()
        return queryset


# ============================================================
# ADMIN PRINCIPAL
# ============================================================


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """Admin mejorado para Order"""

    # ── Lista ─────────────────────────────────────────────
    list_display = (
        "order_id_link",
        "owner_display",
        "order_type",
        "status_badge",
        "measurements_status_badge",
        "items_count",
        "total_display",
        "created_at",
        "actions_column",
    )

    list_filter = (
        OrderStatusFilter,
        OrderTypeFilter,
        MeasurementsStatusFilter,
        HasDesignFilter,
        "created_at",
        "closed",
    )

    search_fields = (
        "id",
        "owner_user__email",
        "owner_user__first_name",
        "owner_user__last_name",
        "owner_team__name",
        "created_by__email",
    )

    list_per_page = 50

    date_hierarchy = "created_at"

    # ── Detalle ───────────────────────────────────────────
    fieldsets = (
        (
            "Información Básica",
            {
                "fields": (
                    "order_type",
                    "status",
                    "created_by",
                    ("owner_user", "owner_team"),
                )
            },
        ),
        (
            "Medidas",
            {
                "fields": (
                    "measurements_open",
                    "measurements_locked",
                    "locked_at",
                    "measurements_due_date",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Diseño",
            {
                "fields": (
                    "design_notes",
                    "design_approved_by",
                    "design_approved_at",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Fechas y Pagos",
            {
                "fields": (
                    "freeze_payment_date",
                    "first_payment_date",
                    "final_payment_date",
                    "uniform_delivery_date",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Cancelación",
            {
                "fields": (
                    "cancelled_at",
                    "cancelled_by",
                    "cancelled_reason",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Metadata",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                    "closed",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    readonly_fields = (
        "created_at",
        "updated_at",
        "locked_at",
        "design_approved_at",
        "production_started_at",
        "delivered_at",
        "cancelled_at",
    )

    raw_id_fields = (
        "owner_user",
        "owner_team",
        "created_by",
        "cancelled_by",
        "design_approved_by",
    )

    inlines = [
        OrderContactInfoInline,
        OrderItemInline,
        OrderDesignImageInline,
        OrderLogInline,
    ]

    # ── Actions ───────────────────────────────────────────
    actions = [
        "export_to_csv",
        "mark_as_pending",
        "close_measurements",
        "lock_measurements",
    ]

    # ── Métodos personalizados ────────────────────────────

    def get_queryset(self, request):
        """Optimizar queryset con agregaciones"""
        qs = super().get_queryset(request)
        return qs.select_related(
            "owner_user",
            "owner_team",
            "created_by",
        ).annotate(
            items_total=Count("items", distinct=True),
            total_amount=Sum("items__subtotal"),
        )

    @admin.display(description="ID", ordering="id")
    def order_id_link(self, obj):
        """ID como link al detalle"""
        url = reverse("admin:orders_order_change", args=[obj.id])
        return format_html('<a href="{}"># {}</a>', url, obj.id)

    @admin.display(description="Propietario")
    def owner_display(self, obj):
        """Muestra el propietario (usuario o equipo)"""
        if obj.order_type == "PERSONAL":
            return obj.owner_user.email if obj.owner_user else "—"
        else:
            return obj.owner_team.name if obj.owner_team else "—"

    @admin.display(description="Estado", ordering="status")
    def status_badge(self, obj):
        """Estado como badge con color"""
        colors = {
            "DRAFT": "gray",
            "PENDING": "orange",
            "DESIGN_APPROVED": "blue",
            "IN_PRODUCTION": "purple",
            "DELIVERED": "green",
            "CANCELLED": "red",
        }
        color = colors.get(obj.status, "gray")
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-size: 11px; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display(),
        )

    @admin.display(description="Medidas")
    def measurements_status_badge(self, obj):
        """Estado de medidas como badge"""
        if obj.measurements_locked:
            return format_html(
                '<span style="background-color: red; color: white; padding: 3px 8px; '
                'border-radius: 3px; font-size: 10px;">🔒 BLOQUEADAS</span>'
            )
        elif not obj.measurements_open:
            return format_html(
                '<span style="background-color: orange; color: white; padding: 3px 8px; '
                'border-radius: 3px; font-size: 10px;">⏸️ CERRADAS</span>'
            )
        else:
            return format_html(
                '<span style="background-color: green; color: white; padding: 3px 8px; '
                'border-radius: 3px; font-size: 10px;">✓ ABIERTAS</span>'
            )

    @admin.display(description="Items", ordering="items_total")
    def items_count(self, obj):
        """Cantidad de items"""
        return obj.items_total if hasattr(obj, "items_total") else obj.items.count()

    @admin.display(description="Total", ordering="total_amount")
    def total_display(self, obj):
        """Total formateado"""
        total = obj.total_amount if hasattr(obj, "total_amount") else obj.total
        return f"${total:,.2f}" if total else "$0.00"

    @admin.display(description="Acciones")
    def actions_column(self, obj):
        """Botones de acción rápida"""
        buttons = []

        # Link a vista de admin custom
        url = reverse("orders:admin_order_detail", args=[obj.id])
        buttons.append(f'<a href="{url}" class="button">📋 Ver Detalle</a>')

        return mark_safe(" ".join(buttons))

    # ── Admin Actions ─────────────────────────────────────

    @admin.action(description="Exportar a CSV")
    def export_to_csv(self, request, queryset):
        """Exportar órdenes seleccionadas a CSV"""
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            f'attachment; filename="orders_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv"'
        )

        writer = csv.writer(response)
        writer.writerow(
            [
                "ID",
                "Tipo",
                "Estado",
                "Propietario",
                "Email",
                "Items",
                "Total",
                "Creada",
                "Medidas Bloqueadas",
            ]
        )

        for order in queryset:
            owner_email = ""
            if order.order_type == "PERSONAL" and order.owner_user:
                owner_email = order.owner_user.email
            elif order.order_type == "TEAM" and order.owner_team:
                owner_email = (
                    order.owner_team.coach.email if order.owner_team.coach else ""
                )

            writer.writerow(
                [
                    order.id,
                    order.get_order_type_display(),
                    order.get_status_display(),
                    order.owner if hasattr(order, "owner") else "",
                    owner_email,
                    order.items.count(),
                    order.total,
                    order.created_at.strftime("%Y-%m-%d %H:%M"),
                    "Sí" if order.measurements_locked else "No",
                ]
            )

        return response

    @admin.action(description="Cerrar medidas (temporal)")
    def close_measurements(self, request, queryset):
        """Cerrar medidas de órdenes seleccionadas"""
        from orders.services.measurements.MeasurementLifecycleService import (
            MeasurementLifecycleService,
        )

        closed = 0
        for order in queryset:
            try:
                MeasurementLifecycleService.close(order, user=request.user)
                closed += 1
            except Exception as e:
                messages.warning(request, f"Orden #{order.id}: {str(e)}")

        self.message_user(
            request, f"{closed} órdenes cerradas correctamente.", messages.SUCCESS
        )

    @admin.action(description="Bloquear medidas (definitivo)")
    def lock_measurements(self, request, queryset):
        """Bloquear medidas definitivamente"""
        from orders.services.measurements.MeasurementLifecycleService import (
            MeasurementLifecycleService,
        )

        locked = 0
        for order in queryset:
            try:
                MeasurementLifecycleService.lock(order, user=request.user)
                locked += 1
            except Exception as e:
                messages.warning(request, f"Orden #{order.id}: {str(e)}")

        self.message_user(
            request, f"{locked} órdenes bloqueadas correctamente.", messages.SUCCESS
        )


# ============================================================
# ADMIN COMPLEMENTARIOS
# ============================================================


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    """Admin para OrderItem"""

    list_display = ("id", "order", "product", "quantity", "unit_price", "subtotal")
    list_filter = ("order__status", "product__product_type")
    search_fields = ("order__id", "product__name")
    raw_id_fields = ("order", "product", "size_variant")


@admin.register(OrderLog)
class OrderLogAdmin(admin.ModelAdmin):
    """Admin para OrderLog (solo lectura)"""

    list_display = (
        "id",
        "order",
        "created_at",
        "user",
        "action",
        "from_status",
        "to_status",
    )
    list_filter = ("action", "created_at")
    search_fields = ("order__id", "user__email")
    readonly_fields = (
        "order",
        "user",
        "action",
        "from_status",
        "to_status",
        "notes",
        "metadata",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

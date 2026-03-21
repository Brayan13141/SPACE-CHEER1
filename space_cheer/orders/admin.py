# orders/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Sum, Q, Prefetch
from django.urls import reverse
from django.utils import timezone
from decimal import Decimal
from .models import (
    Order,
    OrderContactInfo,
    OrderItem,
    OrderItemAthlete,
    OrderItemMeasurement,
    OrderDesignImage,
    OrderItemCustomization,
    OrderLog,
)


# ============================================================
# ORDER CONTACT INFO INLINE
# ============================================================
class OrderContactInfoInline(admin.StackedInline):
    model = OrderContactInfo
    can_delete = False
    fields = (
        ("contact_name", "contact_phone", "contact_email"),
        ("shipping_address_line", "shipping_city", "shipping_postal_code"),
        "shipping_notes",
        ("closed", "created_at", "updated_at"),
    )
    readonly_fields = ("created_at", "updated_at")

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("order")


# ============================================================
# ORDER DESIGN IMAGE INLINE
# ============================================================
class OrderDesignImageInline(admin.TabularInline):
    model = OrderDesignImage
    extra = 0
    fields = ("image", "is_final", "uploaded_by", "created_at", "image_preview")
    readonly_fields = ("created_at", "image_preview", "uploaded_by")
    raw_id_fields = ("uploaded_by",)

    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="max-width: 150px; max-height: 150px; border-radius: 5px;" />',
                obj.image.url,
            )
        return "-"

    image_preview.short_description = "Vista previa"


# ============================================================
# ORDER ITEM MEASUREMENT INLINE
# ============================================================
class OrderItemMeasurementInline(admin.TabularInline):
    model = OrderItemMeasurement
    extra = 0
    fields = ("field_name", "value", "field_unit")
    readonly_fields = ("field_name", "field_unit")

    def has_add_permission(self, request, obj=None):
        return False


# ============================================================
# ORDER ITEM ATHLETE INLINE
# ============================================================
class OrderItemAthleteInline(admin.TabularInline):
    model = OrderItemAthlete
    extra = 0
    fields = ("athlete", "measurement_status", "customization_text")
    raw_id_fields = ("athlete",)
    readonly_fields = ("measurement_status", "customization_text")

    def measurement_status(self, obj):
        if not obj.order_item.product.requires_measurements:
            return format_html('<span style="color: #999;">N/A</span>')

        if obj.has_complete_measurements():
            return format_html('<span style="color: #28a745;">✓ Completo</span>')
        return format_html('<span style="color: #dc3545;">✗ Incompleto</span>')

    measurement_status.short_description = "Medidas"

    def customization_text(self, obj):
        if hasattr(obj, "customization"):
            return obj.customization.custom_text
        return "-"

    customization_text.short_description = "Personalización"


# ============================================================
# ORDER ITEM INLINE
# ============================================================
class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    fields = (
        "product",
        "size_variant",
        "quantity",
        "unit_price",
        "subtotal",
        "config_status",
    )
    readonly_fields = ("unit_price", "subtotal", "config_status")
    raw_id_fields = ("product",)

    def config_status(self, obj):
        state = obj.configuration_state
        if state == "READY":
            return format_html(
                '<span style="color: #28a745; font-weight: bold;">✓ LISTO</span>'
            )
        return format_html(
            '<span style="color: #ffc107; font-weight: bold;">⚠ INCOMPLETO</span>'
        )

    config_status.short_description = "Estado"


# ============================================================
# ORDER LOG INLINE
# ============================================================
class OrderLogInline(admin.TabularInline):
    model = OrderLog
    extra = 0
    fields = ("action", "from_status", "to_status", "user", "notes", "created_at")
    readonly_fields = (
        "action",
        "from_status",
        "to_status",
        "user",
        "notes",
        "created_at",
        "metadata",
    )
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


# ============================================================
# ORDER ADMIN - EL MONSTRUO
# ============================================================
@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "order_number",
        "order_type_badge",
        "owner_display",
        "status_badge",
        "total_display",
        "item_count",
        "measurements_status",
        "created_at",
        "quick_actions",
    )
    list_filter = (
        "status",
        "order_type",
        "closed",
        "measurements_locked",
        ("created_at", admin.DateFieldListFilter),
        ("measurements_due_date", admin.DateFieldListFilter),
    )
    search_fields = (
        "id",
        "owner_user__username",
        "owner_user__email",
        "owner_team__name",
        "created_by__username",
        "created_by__email",
    )
    raw_id_fields = (
        "owner_user",
        "owner_team",
        "created_by",
        "design_approved_by",
        "cancelled_by",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
        "locked_at",
        "design_approved_at",
        "production_started_at",
        "delivered_at",
        "cancelled_at",
        "total_display",
        "item_summary",
        "athlete_summary",
        "timeline_visual",
    )
    date_hierarchy = "created_at"
    ordering = ("-created_at",)

    # Inlines
    inlines = [
        OrderContactInfoInline,
        OrderItemInline,
        OrderDesignImageInline,
        OrderLogInline,
    ]

    # Fieldsets organizados por lógica de negocio
    fieldsets = (
        (
            "Información Básica",
            {
                "fields": (
                    ("order_type", "status"),
                    ("owner_user", "owner_team"),
                    "created_by",
                )
            },
        ),
        (
            "Contenido de la Orden",
            {
                "fields": ("design_notes", "item_summary", "total_display"),
            },
        ),
        (
            "Medidas y Configuración",
            {
                "fields": (
                    ("measurements_open", "measurements_locked", "locked_at"),
                    "measurements_due_date",
                    "athlete_summary",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Diseño",
            {
                "fields": (("design_approved_by", "design_approved_at"),),
                "classes": ("collapse",),
            },
        ),
        (
            "Pagos",
            {
                "fields": (
                    "freeze_payment_date",
                    "first_payment_date",
                    "final_payment_date",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Fechas Operativas",
            {
                "fields": (
                    "uniform_delivery_date",
                    ("production_started_at", "delivered_at"),
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Cancelación",
            {
                "fields": (
                    ("cancelled_by", "cancelled_at"),
                    "cancelled_reason",
                ),
                "classes": ("collapse",),
            },
        ),
        ("Timeline", {"fields": ("timeline_visual",), "classes": ("collapse",)}),
        (
            "Sistema",
            {
                "fields": (
                    "closed",
                    ("created_at", "updated_at"),
                ),
                "classes": ("collapse",),
            },
        ),
    )

    # Acciones bulk
    actions = [
        "cancel_orders",
        "lock_measurements",
        "unlock_measurements",
        "export_to_csv",
    ]

    # ============ MÉTODOS DE DISPLAY ============

    def order_number(self, obj):
        return f"#{obj.id}"

    order_number.short_description = "Orden"
    order_number.admin_order_field = "id"

    def order_type_badge(self, obj):
        colors = {
            "PERSONAL": "#007bff",
            "TEAM": "#28a745",
        }
        icons = {
            "PERSONAL": "👤",
            "TEAM": "👥",
        }
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 8px; border-radius: 3px; font-size: 11px;">{} {}</span>',
            colors[obj.order_type],
            icons[obj.order_type],
            obj.get_order_type_display(),
        )

    order_type_badge.short_description = "Tipo"

    def owner_display(self, obj):
        if obj.order_type == "PERSONAL":
            url = reverse("admin:accounts_user_change", args=[obj.owner_user.id])
            return format_html(
                '<a href="{}">{}</a>',
                url,
                obj.owner_user.get_full_name() or obj.owner_user.username,
            )
        else:
            url = reverse("admin:teams_team_change", args=[obj.owner_team.id])
            return format_html('<a href="{}">{}</a>', url, obj.owner_team.name)

    owner_display.short_description = "Propietario"

    def status_badge(self, obj):
        colors = {
            "DRAFT": "#6c757d",
            "PENDING": "#ffc107",
            "DESIGN_APPROVED": "#17a2b8",
            "IN_PRODUCTION": "#007bff",
            "DELIVERED": "#28a745",
            "CANCELLED": "#dc3545",
        }
        color = colors.get(obj.status, "#6c757d")

        # Agregar indicador si está cerrada
        closed_indicator = " 🔒" if obj.closed else ""

        return format_html(
            '<span style="background: {}; color: white; padding: 4px 10px; border-radius: 3px; font-weight: bold; font-size: 11px;">{}{}</span>',
            color,
            obj.get_status_display(),
            closed_indicator,
        )

    status_badge.short_description = "Estado"

    def total_display(self, obj):
        total = obj.total
        if total > 0:
            return format_html(
                '<span style="font-size: 16px; font-weight: bold; color: #28a745;">${:,.2f} MXN</span>',
                total,
            )
        return format_html('<span style="color: #999;">$0.00</span>')

    total_display.short_description = "Total"

    def item_count(self, obj):
        count = obj.items.count()
        if count == 0:
            return format_html('<span style="color: #999;">0</span>')
        return format_html("<strong>{}</strong>", count)

    item_count.short_description = "Items"
    item_count.admin_order_field = "item_count_annotated"

    def measurements_status(self, obj):
        if not obj.measurements_locked:
            if obj.measurements_open:
                return format_html('<span style="color: #28a745;">🟢 Abierto</span>')
            return format_html('<span style="color: #ffc107;">🟡 Cerrado temp.</span>')
        return format_html('<span style="color: #dc3545;">🔒 Bloqueado</span>')

    measurements_status.short_description = "Medidas"

    def quick_actions(self, obj):
        """Links rápidos a acciones comunes"""
        url = reverse("admin:orders_order_change", args=[obj.id])
        return format_html('<a href="{}">✏️ Editar</a>', url)

    quick_actions.short_description = "Acciones"

    def item_summary(self, obj):
        """Resumen de productos en la orden"""
        items = obj.items.select_related("product", "size_variant").prefetch_related(
            "athletes"
        )

        if not items:
            return format_html('<p style="color: #999;">Sin productos agregados</p>')

        html = '<table style="width: 100%; border-collapse: collapse;">'
        html += '<tr style="background: #f0f0f0; font-weight: bold;"><th>Producto</th><th>Talla</th><th>Cant.</th><th>Precio Unit.</th><th>Subtotal</th><th>Estado</th></tr>'

        for item in items:
            config_status = (
                "✓ Listo" if item.configuration_state == "READY" else "⚠ Incompleto"
            )
            config_color = (
                "#28a745" if item.configuration_state == "READY" else "#ffc107"
            )

            html += f"""
            <tr>
                <td>{item.product.name}</td>
                <td>{item.size_variant.size if item.size_variant else "-"}</td>
                <td style="text-align: center;">{item.quantity}</td>
                <td>${item.unit_price:,.2f}</td>
                <td style="font-weight: bold;">${item.subtotal:,.2f}</td>
                <td style="color: {config_color};">{config_status}</td>
            </tr>
            """

        html += "</table>"
        return format_html(html)

    item_summary.short_description = "Productos"

    def athlete_summary(self, obj):
        """Resumen de atletas y sus medidas"""
        athletes = (
            OrderItemAthlete.objects.filter(order_item__order=obj)
            .select_related("athlete", "order_item__product")
            .prefetch_related("measurements")
        )

        if not athletes:
            return format_html('<p style="color: #999;">Sin atletas asignados</p>')

        html = (
            '<table style="width: 100%; border-collapse: collapse; font-size: 12px;">'
        )
        html += '<tr style="background: #f0f0f0; font-weight: bold;"><th>Atleta</th><th>Producto</th><th>Medidas</th></tr>'

        for athlete_item in athletes:
            status = (
                "✓ Completo"
                if athlete_item.has_complete_measurements()
                else "✗ Incompleto"
            )
            color = "#28a745" if athlete_item.has_complete_measurements() else "#dc3545"

            html += f"""
            <tr>
                <td>{athlete_item.athlete.get_full_name()}</td>
                <td>{athlete_item.order_item.product.name}</td>
                <td style="color: {color};">{status}</td>
            </tr>
            """

        html += "</table>"
        return format_html(html)

    athlete_summary.short_description = "Atletas y medidas"

    def timeline_visual(self, obj):
        """Timeline visual del ciclo de vida de la orden"""
        events = []

        if obj.created_at:
            events.append(("Creada", obj.created_at, "#6c757d"))

        if obj.freeze_payment_date:
            events.append(("Pago congelación", obj.freeze_payment_date, "#007bff"))

        if obj.design_approved_at:
            events.append(("Diseño aprobado", obj.design_approved_at, "#17a2b8"))

        if obj.locked_at:
            events.append(("Medidas bloqueadas", obj.locked_at, "#ffc107"))

        if obj.first_payment_date:
            events.append(("Primer pago", obj.first_payment_date, "#28a745"))

        if obj.production_started_at:
            events.append(("Producción iniciada", obj.production_started_at, "#007bff"))

        if obj.delivered_at:
            events.append(("Entregada", obj.delivered_at, "#28a745"))

        if obj.cancelled_at:
            events.append(("Cancelada", obj.cancelled_at, "#dc3545"))

        html = '<div style="position: relative; padding: 20px 0;">'

        for i, (label, date, color) in enumerate(events):
            html += f"""
            <div style="position: relative; margin-bottom: 15px; padding-left: 30px;">
                <div style="position: absolute; left: 0; top: 0; width: 12px; height: 12px; background: {color}; border-radius: 50%; border: 3px solid white; box-shadow: 0 0 0 1px {color};"></div>
                {f'<div style="position: absolute; left: 5px; top: 12px; width: 2px; height: 15px; background: #ddd;"></div>' if i < len(events) - 1 else ''}
                <strong>{label}</strong><br>
                <span style="color: #666; font-size: 12px;">{date.strftime("%d/%m/%Y %H:%M")}</span>
            </div>
            """

        html += "</div>"
        return format_html(html)

    timeline_visual.short_description = "Timeline"

    def get_queryset(self, request):
        """Optimización brutal de queries"""
        return (
            super()
            .get_queryset(request)
            .select_related(
                "owner_user",
                "owner_team",
                "created_by",
                "design_approved_by",
                "cancelled_by",
            )
            .prefetch_related(
                Prefetch(
                    "items",
                    queryset=OrderItem.objects.select_related(
                        "product", "size_variant"
                    ),
                ),
            )
            .annotate(item_count_annotated=Count("items", distinct=True))
        )

    # ============ ACCIONES BULK ============

    @admin.action(description="✗ Cancelar órdenes seleccionadas")
    def cancel_orders(self, request, queryset):
        """Cancelar múltiples órdenes (solo DRAFT/PENDING)"""
        allowed = queryset.filter(status__in=["DRAFT", "PENDING"])
        count = allowed.update(
            status="CANCELLED",
            cancelled_at=timezone.now(),
            cancelled_by=request.user,
            cancelled_reason="Cancelación masiva desde admin",
            closed=True,
        )
        self.message_user(request, f"{count} órdenes canceladas correctamente.")

        if queryset.count() > count:
            self.message_user(
                request,
                f"{queryset.count() - count} órdenes no se pudieron cancelar (estado no permitido).",
                level="warning",
            )

    @admin.action(description="🔒 Bloquear medidas de órdenes seleccionadas")
    def lock_measurements(self, request, queryset):
        count = queryset.filter(measurements_locked=False).update(
            measurements_locked=True, measurements_open=False, locked_at=timezone.now()
        )
        self.message_user(request, f"Medidas bloqueadas en {count} órdenes.")

    @admin.action(description="🔓 Desbloquear medidas de órdenes seleccionadas")
    def unlock_measurements(self, request, queryset):
        count = queryset.update(
            measurements_locked=False, measurements_open=True, locked_at=None
        )
        self.message_user(request, f"Medidas desbloqueadas en {count} órdenes.")

    @admin.action(description="📊 Exportar a CSV")
    def export_to_csv(self, request, queryset):
        """Exportar órdenes a CSV"""
        import csv
        from django.http import HttpResponse

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            f'attachment; filename="ordenes_{timezone.now().strftime("%Y%m%d")}.csv"'
        )

        writer = csv.writer(response)
        writer.writerow(
            ["ID", "Tipo", "Propietario", "Estado", "Total", "Creada", "Actualizada"]
        )

        for order in queryset:
            owner = order.owner_user or order.owner_team
            writer.writerow(
                [
                    order.id,
                    order.get_order_type_display(),
                    str(owner),
                    order.get_status_display(),
                    order.total,
                    order.created_at.strftime("%Y-%m-%d %H:%M"),
                    order.updated_at.strftime("%Y-%m-%d %H:%M"),
                ]
            )

        return response


# ============================================================
# ORDER ITEM ADMIN
# ============================================================
@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = (
        "order_link",
        "product",
        "size_variant",
        "quantity",
        "unit_price",
        "subtotal",
        "config_badge",
    )
    list_filter = ("product__product_type", "product__usage_type")
    search_fields = ("order__id", "product__name")
    raw_id_fields = ("order", "product", "size_variant")
    readonly_fields = ("unit_price", "subtotal")

    inlines = [OrderItemAthleteInline]

    def order_link(self, obj):
        url = reverse("admin:orders_order_change", args=[obj.order.id])
        return format_html('<a href="{}">Orden #{}</a>', url, obj.order.id)

    order_link.short_description = "Orden"

    def config_badge(self, obj):
        state = obj.configuration_state
        if state == "READY":
            return format_html(
                '<span style="color: #28a745; font-weight: bold;">✓ LISTO</span>'
            )
        return format_html(
            '<span style="color: #ffc107; font-weight: bold;">⚠ INCOMPLETO</span>'
        )

    config_badge.short_description = "Configuración"


class RequiresMeasurementsFilter(admin.SimpleListFilter):
    title = "Requires measurements"
    parameter_name = "requires_measurements"

    def lookups(self, request, model_admin):
        return (
            ("yes", "Yes"),
            ("no", "No"),
        )

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.filter(order_item__product__requires_measurements=True)
        if self.value() == "no":
            return queryset.filter(order_item__product__requires_measurements=False)
        return queryset


# ============================================================
# ORDER ITEM ATHLETE ADMIN
# ============================================================
@admin.register(OrderItemAthlete)
class OrderItemAthleteAdmin(admin.ModelAdmin):
    list_display = (
        "athlete",
        "order_item",
        "measurement_badge",
        "customization_preview",
    )
    list_filter = [RequiresMeasurementsFilter]
    search_fields = ("athlete__username", "athlete__email", "order_item__order__id")
    raw_id_fields = ("order_item", "athlete")

    inlines = [OrderItemMeasurementInline]

    def measurement_badge(self, obj):
        if not obj.order_item.product.requires_measurements:
            return format_html('<span style="color: #999;">N/A</span>')

        if obj.has_complete_measurements():
            return format_html(
                '<span style="color: #28a745; font-weight: bold;">✓ Completo</span>'
            )
        return format_html(
            '<span style="color: #dc3545; font-weight: bold;">✗ Incompleto</span>'
        )

    measurement_badge.short_description = "Medidas"

    def customization_preview(self, obj):
        if hasattr(obj, "customization"):
            return obj.customization.custom_text
        return "-"

    customization_preview.short_description = "Personalización"

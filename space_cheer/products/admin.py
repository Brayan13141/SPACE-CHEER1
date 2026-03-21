# products/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Sum, Prefetch
from django.urls import reverse
from django.core.exceptions import ValidationError
from decimal import Decimal
from django.utils.encoding import force_str
from .models import Season, Product, ProductMeasurementField, ProductSizeVariant
from decimal import Decimal, InvalidOperation
from orders.models import OrderItem


# ============================================================
# HELPERS PARA CONVERSIÓN SEGURA
# ============================================================


def format_currency(value):
    """Convierte cualquier cosa a string formateado seguro"""
    if value is None:
        value = Decimal("0.00")

    # Asegurar que es número
    if not isinstance(value, (int, float, Decimal)):
        value = Decimal(str(value))

    return f"{value:,.2f}"


def safe_decimal_from_aggregate(aggregate_dict, key="total", default="0.00"):
    """
    Convierte resultado de aggregate a Decimal de forma 100% segura.

    Maneja:
    - None
    - SafeString
    - String vacío
    - Cualquier tipo raro de serialización/caché

    Args:
        aggregate_dict: Resultado de .aggregate()
        key: Clave del aggregate (default "total")
        default: Valor por defecto si falla (default "0.00")

    Returns:
        Decimal garantizado
    """
    value = aggregate_dict.get(key)

    if value is None:
        return Decimal(default)

    try:
        # Forzar a string nativo de Python
        str_value = force_str(value)

        # Limpiar whitespace
        str_value = str_value.strip()

        # Si es vacío, retornar default
        if not str_value:
            return Decimal(default)

        # Convertir a Decimal
        return Decimal(str_value)

    except (ValueError, TypeError, InvalidOperation, AttributeError):
        # Cualquier error = retornar default
        return Decimal(default)


def safe_float_for_format(decimal_value):
    """
    Convierte Decimal a float nativo de Python para formateo.

    Args:
        decimal_value: Decimal o cualquier número

    Returns:
        float de Python puro
    """
    try:
        return float(decimal_value)
    except (ValueError, TypeError):
        return 0.0


# ============================================================
# SEASON ADMIN
# ============================================================


@admin.register(Season)
class SeasonAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "status_badge",
        "product_count",
        "total_revenue_estimate",
    )
    list_filter = ("is_active",)
    search_fields = ("name",)
    ordering = ("-is_active", "name")

    actions = ["activate_seasons", "deactivate_seasons"]

    def status_badge(self, obj):
        """Badge visual del estado de la temporada"""
        if obj.is_active:
            return format_html(
                '<span style="background: #28a745; color: white; padding: 3px 12px; '
                'border-radius: 3px; font-weight: bold;">✓ ACTIVA</span>'
            )
        return format_html(
            '<span style="background: #6c757d; color: white; padding: 3px 12px; '
            'border-radius: 3px;">○ Inactiva</span>'
        )

    status_badge.short_description = "Estado"
    status_badge.admin_order_field = "is_active"

    def product_count(self, obj):
        """Número de productos en esta temporada"""
        count = obj.product_set.count()
        if count == 0:
            return format_html('<span style="color: #999;">0 productos</span>')

        url = (
            reverse("admin:products_product_changelist")
            + f"?season__id__exact={obj.id}"
        )

        # Contar por tipo
        active = obj.product_set.filter(is_active=True).count()
        inactive = count - active

        return format_html(
            '<a href="{}" style="font-weight: bold;">{}</a> '
            '<span style="color: #28a745;">({}✓)</span> '
            '<span style="color: #999;">({}✗)</span>',
            url,
            count,
            active,
            inactive,
        )

    product_count.short_description = "Productos (activos/inactivos)"
    product_count.admin_order_field = "product_count_annotated"

    def total_revenue_estimate(self, obj):

        real_agg = OrderItem.objects.filter(
            product__season=obj, order__status="DELIVERED"
        ).aggregate(total=Sum("subtotal"))

        real_revenue = safe_decimal_from_aggregate(real_agg)

        potential_agg = OrderItem.objects.filter(
            product__season=obj,
            order__status__in=["DRAFT", "PENDING", "DESIGN_APPROVED", "IN_PRODUCTION"],
        ).aggregate(total=Sum("subtotal"))

        potential = safe_decimal_from_aggregate(potential_agg)

        if real_revenue == Decimal("0.00") and potential == Decimal("0.00"):
            return format_html('<span style="color: #999;">$0.00</span>')

        #  FORMATEAR ANTES
        real_str = format_currency(real_revenue)
        potential_str = format_currency(potential)

        return format_html(
            '<div style="line-height: 1.6;">'
            '<strong style="color: #28a745; font-size: 14px;">${}</strong> '
            '<small style="color: #666;">real</small><br>'
            '<span style="color: #007bff;">${}</span> '
            '<small style="color: #666;">potencial</small>'
            "</div>",
            real_str,
            potential_str,
        )

    total_revenue_estimate.short_description = "Revenue"

    def get_queryset(self, request):
        """Optimizar con anotaciones"""
        qs = super().get_queryset(request)
        return qs.annotate(product_count_annotated=Count("product", distinct=True))

    # ============ ACCIONES BULK ============

    @admin.action(description="✓ Activar temporadas seleccionadas")
    def activate_seasons(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} temporadas activadas.")

    @admin.action(description="✗ Desactivar temporadas seleccionadas")
    def deactivate_seasons(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(
            request,
            f"{updated} temporadas desactivadas. No se pueden crear nuevos productos.",
            level="warning",
        )


# ============================================================
# PRODUCT MEASUREMENT FIELD INLINE
# ============================================================
class ProductMeasurementFieldInline(admin.TabularInline):
    model = ProductMeasurementField
    extra = 1
    fields = ("field", "required", "field_preview")
    readonly_fields = ("field_preview",)
    raw_id_fields = ("field",)

    def field_preview(self, obj):
        """Preview del campo de medida"""
        if obj.field:
            return format_html(
                '<strong>{}</strong> <span style="color: #666;">({} - {})</span>',
                obj.field.name,
                obj.field.get_field_type_display(),
                obj.field.unit or "sin unidad",
            )
        return "-"

    field_preview.short_description = "Campo"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("field")


# ============================================================
# PRODUCT SIZE VARIANT INLINE
# ============================================================
class ProductSizeVariantInline(admin.TabularInline):
    model = ProductSizeVariant
    extra = 1
    fields = ("size", "additional_price", "final_price_preview")
    readonly_fields = ("final_price_preview",)

    def final_price_preview(self, obj):
        """Preview del precio final"""
        if obj.product and obj.additional_price is not None:
            base = obj.product.base_price
            final = base + obj.additional_price

            if obj.additional_price > 0:
                return format_html(
                    '<span style="color: #666;">${:,.2f}</span> + '
                    '<span style="color: #007bff;">${:,.2f}</span> = '
                    '<strong style="color: #28a745;">${:,.2f}</strong>',
                    base,
                    obj.additional_price,
                    final,
                )
            return format_html(
                '<strong style="color: #28a745;">${:,.2f}</strong>', final
            )
        return "-"

    final_price_preview.short_description = "Precio final"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("product")


# ============================================================
# PRODUCT ADMIN - EL CEREBRO DEL SISTEMA
# ============================================================
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "product_type_badge",
        "usage_badge",
        "strategy_badge",
        "scope_badge",
        "config_status",
        "price_display",
        "season",
        "active_status",
        "order_count",
    )
    list_filter = (
        "is_active",
        "product_type",
        "usage_type",
        "size_strategy",
        "scope",
        "is_configured",
        "season",
        ("created_at", admin.DateFieldListFilter),
    )
    search_fields = (
        "name",
        "description",
        "season__name",
        "owner_team__name",
    )
    raw_id_fields = ("owner_team",)
    readonly_fields = (
        "created_at",
        "is_configured",
        "configuration_summary",
        "business_rules_check",
        "usage_stats",
        "revenue_stats",
    )
    ordering = ("-created_at",)
    date_hierarchy = "created_at"

    # Inlines
    inlines = [ProductSizeVariantInline, ProductMeasurementFieldInline]

    # Fieldsets organizados por lógica de negocio
    fieldsets = (
        ("Información Básica", {"fields": ("name", "description", "image")}),
        (
            "Clasificación del Producto",
            {
                "fields": (
                    ("product_type", "season"),
                    ("usage_type", "size_strategy"),
                    ("scope", "owner_team"),
                ),
                "description": (
                    "<strong>⚠️ ADVERTENCIA:</strong> Los campos de clasificación NO se pueden "
                    "cambiar después de usar el producto en una orden. Configura correctamente desde el inicio."
                ),
            },
        ),
        ("Precio", {"fields": ("base_price",)}),
        ("Estado", {"fields": ("is_active", "is_configured")}),
        (
            "Validación y Reglas de Negocio",
            {
                "fields": ("business_rules_check", "configuration_summary"),
                "classes": ("collapse",),
            },
        ),
        (
            "Estadísticas de Uso",
            {"fields": ("usage_stats", "revenue_stats"), "classes": ("collapse",)},
        ),
        ("Sistema", {"fields": ("created_at",), "classes": ("collapse",)}),
    )

    # Acciones bulk
    actions = [
        "activate_products",
        "deactivate_products",
        "mark_as_configured",
        "duplicate_products",
        "export_catalog",
    ]

    # ============ MÉTODOS DE DISPLAY ============

    def product_type_badge(self, obj):
        """Badge del tipo de producto"""
        colors = {
            "UNIFORM": "#007bff",
            "SHOES": "#28a745",
            "BAG": "#ffc107",
            "OTHER": "#6c757d",
        }
        icons = {
            "UNIFORM": "👕",
            "SHOES": "👟",
            "BAG": "🎒",
            "OTHER": "📦",
        }
        color = colors.get(obj.product_type, "#6c757d")
        icon = icons.get(obj.product_type, "")

        return format_html(
            '<span style="background: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-size: 11px;">{} {}</span>',
            color,
            icon,
            obj.get_product_type_display(),
        )

    product_type_badge.short_description = "Tipo"
    product_type_badge.admin_order_field = "product_type"

    def usage_badge(self, obj):
        """Badge del tipo de uso"""
        colors = {
            "GLOBAL": "#6c757d",
            "TEAM_CUSTOM": "#17a2b8",
            "ATHLETE_CUSTOM": "#dc3545",
        }
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-size: 10px;">{}</span>',
            colors.get(obj.usage_type, "#6c757d"),
            obj.get_usage_type_display(),
        )

    usage_badge.short_description = "Uso"
    usage_badge.admin_order_field = "usage_type"

    def strategy_badge(self, obj):
        """Badge de estrategia de talla"""
        colors = {
            "NONE": "#6c757d",
            "STANDARD": "#28a745",
            "MEASUREMENTS": "#007bff",
        }
        icons = {
            "NONE": "○",
            "STANDARD": "📏",
            "MEASUREMENTS": "📐",
        }
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-size: 10px;">{} {}</span>',
            colors.get(obj.size_strategy, "#6c757d"),
            icons.get(obj.size_strategy, ""),
            obj.get_size_strategy_display(),
        )

    strategy_badge.short_description = "Tallas"
    strategy_badge.admin_order_field = "size_strategy"

    def scope_badge(self, obj):
        """Badge de alcance"""
        if obj.scope == "CATALOG":
            return format_html(
                '<span style="background: #28a745; color: white; padding: 2px 6px; '
                'border-radius: 3px; font-size: 10px;">🌐 Catálogo</span>'
            )

        # Para team-only, usar placeholder {}
        team_name = obj.owner_team.name if obj.owner_team else "?"
        return format_html(
            '<span style="background: #ffc107; color: #000; padding: 2px 6px; '
            'border-radius: 3px; font-size: 10px;">🔒 {}</span>',
            team_name,  # ← Se pasa DESPUÉS del template string
        )

    scope_badge.short_description = "Alcance"

    def config_status(self, obj):
        """Estado de configuración visual"""
        if obj.is_configured:
            return format_html(
                '<span style="background: #28a745; color: white; padding: 4px 10px; '
                'border-radius: 3px; font-weight: bold;">✓ CONFIGURADO</span>'
            )

        # Determinar qué falta
        missing = []
        if obj.size_strategy == "STANDARD" and not obj.size_variants.exists():
            missing.append("tallas")
        if obj.size_strategy == "MEASUREMENTS" and not obj.measurement_fields.exists():
            missing.append("campos de medida")

        missing_text = ", ".join(missing) if missing else "configuración"

        return format_html(
            '<span style="background: #dc3545; color: white; padding: 4px 10px; '
            'border-radius: 3px; font-weight: bold;">✗ Falta: {}</span>',
            missing_text,
        )

    config_status.short_description = "Configuración"
    config_status.admin_order_field = "is_configured"

    def price_display(self, obj):
        price_str = format_currency(obj.base_price)
        """Display del precio con formato"""
        return format_html(
            '<span style="font-weight: bold; color: #28a745; font-size: 13px;">${}</span>',
            price_str,
        )

    price_display.short_description = "Precio base"
    price_display.admin_order_field = "base_price"

    def active_status(self, obj):
        """Badge de estado activo/inactivo"""
        if obj.is_active:
            return format_html(
                '<span style="color: #28a745; font-weight: bold;">✓</span>'
            )
        return format_html('<span style="color: #dc3545; font-weight: bold;">✗</span>')

    active_status.short_description = "Activo"
    active_status.admin_order_field = "is_active"

    def order_count(self, obj):
        """Número de veces que se ha usado en órdenes"""
        from orders.models import OrderItem

        count = OrderItem.objects.filter(product=obj).count()

        if count == 0:
            return format_html('<span style="color: #999;">0</span>')

        # Contar por estado de orden
        delivered = OrderItem.objects.filter(
            product=obj, order__status="DELIVERED"
        ).count()
        active = OrderItem.objects.filter(
            product=obj,
            order__status__in=["DRAFT", "PENDING", "DESIGN_APPROVED", "IN_PRODUCTION"],
        ).count()

        url = (
            reverse("admin:orders_orderitem_changelist")
            + f"?product__id__exact={obj.id}"
        )

        return format_html(
            '<a href="{}" style="font-weight: bold;">{}</a> '
            '<small style="color: #666;">({}✓ {}⏳)</small>',
            url,
            count,
            delivered,
            active,
        )

    order_count.short_description = "Órdenes (entregadas/activas)"
    order_count.admin_order_field = "order_count_annotated"

    def configuration_summary(self, obj):
        """Resumen visual de la configuración del producto"""
        html = '<div style="line-height: 2; font-size: 13px;">'

        # Propiedades computadas
        props = [
            ("Requiere diseño", obj.requires_design, "#17a2b8"),
            ("Requiere atletas", obj.requires_athletes, "#007bff"),
            ("Requiere medidas", obj.requires_measurements, "#dc3545"),
            ("Requiere tallas", obj.requires_sizes, "#28a745"),
            ("Requiere equipo", obj.requires_team, "#ffc107"),
            ("Es simple", obj.is_simple, "#6c757d"),
        ]

        for label, value, color in props:
            icon = "✓" if value else "✗"
            style = f"color: {color}; font-weight: bold;" if value else "color: #ccc;"
            html += f'<div><span style="{style}">{icon}</span> {label}</div>'

        # Configuración de tallas
        if obj.size_strategy == "STANDARD":
            variants = obj.size_variants.all()
            if variants:
                sizes = ", ".join([v.size for v in variants])
                html += (
                    f'<div style="margin-top: 10px; padding: 5px; background: #f0f0f0; border-radius: 3px;">'
                    f"<strong>Tallas:</strong> {sizes}</div>"
                )

        # Configuración de medidas
        if obj.size_strategy == "MEASUREMENTS":
            fields = obj.measurement_fields.select_related("field").all()
            if fields:
                field_names = ", ".join([f.field.name for f in fields])
                html += (
                    f'<div style="margin-top: 10px; padding: 5px; background: #f0f0f0; border-radius: 3px;">'
                    f"<strong>Campos de medida:</strong> {field_names}</div>"
                )

        html += "</div>"
        return format_html(html)

    configuration_summary.short_description = "Resumen de configuración"

    def business_rules_check(self, obj):
        """Verificación de reglas de negocio"""
        try:
            # Intentar validar
            obj.full_clean()
            return format_html(
                '<div style="padding: 10px; background: #d4edda; color: #155724; '
                'border-radius: 5px; border: 1px solid #c3e6cb;">'
                "<strong>✓ VÁLIDO:</strong> Todas las reglas de negocio se cumplen."
                "</div>"
            )
        except ValidationError as e:
            errors_html = "<ul style='margin: 5px 0; padding-left: 20px;'>"
            if hasattr(e, "message_dict"):
                for field, messages in e.message_dict.items():
                    for message in messages:
                        errors_html += f"<li><strong>{field}:</strong> {message}</li>"
            else:
                for message in e.messages:
                    errors_html += f"<li>{message}</li>"
            errors_html += "</ul>"

            return format_html(
                '<div style="padding: 10px; background: #f8d7da; color: #721c24; '
                'border-radius: 5px; border: 1px solid #f5c6cb;">'
                "<strong>✗ ERRORES DE VALIDACIÓN:</strong>{}"
                "</div>",
                errors_html,
            )

    business_rules_check.short_description = "Validación de reglas de negocio"

    def usage_stats(self, obj):
        """Estadísticas de uso del producto"""
        from orders.models import OrderItem

        items = OrderItem.objects.filter(product=obj).select_related("order")

        if not items.exists():
            return format_html('<p style="color: #999;">Producto sin uso</p>')

        # Estadísticas por estado
        stats = {}
        for status_code, status_label in [
            ("DRAFT", "Borrador"),
            ("PENDING", "Pendiente"),
            ("DESIGN_APPROVED", "Diseño aprobado"),
            ("IN_PRODUCTION", "En producción"),
            ("DELIVERED", "Entregado"),
            ("CANCELLED", "Cancelado"),
        ]:
            count = items.filter(order__status=status_code).count()
            if count > 0:
                stats[status_label] = count

        # Total de unidades
        total_quantity = items.aggregate(total=Sum("quantity"))["total"] or 0

        html = '<div style="font-size: 12px; line-height: 1.8;">'
        html += f"<strong>Total unidades vendidas:</strong> {total_quantity}<br><br>"

        if stats:
            html += '<strong>Por estado de orden:</strong><ul style="margin: 5px 0; padding-left: 20px;">'
            for status, count in stats.items():
                html += f"<li>{status}: {count}</li>"
            html += "</ul>"

        html += "</div>"
        return format_html(html)

    usage_stats.short_description = "Estadísticas de uso"

    def revenue_stats(self, obj):
        """Estadísticas de ingresos - VERSIÓN FIJA"""
        from orders.models import OrderItem

        items = OrderItem.objects.filter(product=obj)

        if not items.exists():
            return format_html('<p style="color: #999;">Sin ingresos registrados</p>')

        # Revenue por estado - CON CONVERSIÓN SEGURA
        delivered_agg = items.filter(order__status="DELIVERED").aggregate(
            total=Sum("subtotal")
        )
        delivered_revenue = delivered_agg.get("total")

        if delivered_revenue is None or delivered_revenue == "":
            delivered_revenue = Decimal("0.00")
        else:
            delivered_revenue = Decimal(str(delivered_revenue))

        active_agg = items.filter(
            order__status__in=["DRAFT", "PENDING", "DESIGN_APPROVED", "IN_PRODUCTION"]
        ).aggregate(total=Sum("subtotal"))

        active_revenue = active_agg.get("total")

        if active_revenue is None or active_revenue == "":
            active_revenue = Decimal("0.00")
        else:
            active_revenue = Decimal(str(active_revenue))

        total_revenue = delivered_revenue + active_revenue

        # CONVERTIR A FLOAT ANTES DE FORMATEAR
        return format_html(
            '<div style="line-height: 2;">'
            '<strong style="font-size: 16px; color: #28a745;">${:,.2f}</strong> '
            '<span style="color: #666;">total</span><br>'
            '<div style="font-size: 12px; color: #666;">'
            "  └ ${:,.2f} entregado<br>"
            "  └ ${:,.2f} en proceso"
            "</div>"
            "</div>",
            float(total_revenue),
            float(delivered_revenue),
            float(active_revenue),
        )

    revenue_stats.short_description = "Ingresos generados"

    def get_queryset(self, request):
        """Optimización BRUTAL de queries"""
        from orders.models import OrderItem

        qs = super().get_queryset(request)

        return (
            qs.select_related(
                "season",
                "owner_team",
            )
            .prefetch_related(
                Prefetch(
                    "size_variants",
                    queryset=ProductSizeVariant.objects.order_by("size"),
                ),
                Prefetch(
                    "measurement_fields",
                    queryset=ProductMeasurementField.objects.select_related("field"),
                ),
            )
            .annotate(order_count_annotated=Count("orderitem", distinct=True))
        )

    # ============ ACCIONES BULK ============

    @admin.action(description="✓ Activar productos seleccionados")
    def activate_products(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} productos activados.")

    @admin.action(description="✗ Desactivar productos seleccionados")
    def deactivate_products(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} productos desactivados.")

    @admin.action(description="⚙️ Marcar como configurados")
    def mark_as_configured(self, request, queryset):
        """Recalcular estado de configuración"""
        count = 0
        for product in queryset:
            product.update_configuration_status()
            count += 1
        self.message_user(
            request, f"Estado de configuración actualizado para {count} productos."
        )

    @admin.action(description="📋 Duplicar productos seleccionados")
    def duplicate_products(self, request, queryset):
        """Duplicar productos (útil para variantes)"""
        duplicated = 0

        for product in queryset:
            # Guardar relaciones antes de duplicar
            old_variants = list(product.size_variants.all())
            old_fields = list(product.measurement_fields.all())

            # Duplicar producto
            product.pk = None
            product.name = f"{product.name} (Copia)"
            product.is_configured = False
            product.save()

            # Duplicar tallas
            for variant in old_variants:
                variant.pk = None
                variant.product = product
                variant.save()

            # Duplicar campos de medida
            for field_rel in old_fields:
                field_rel.pk = None
                field_rel.product = product
                field_rel.save()

            product.update_configuration_status()
            duplicated += 1

        self.message_user(
            request,
            f"{duplicated} productos duplicados correctamente. "
            "Recuerda revisar y actualizar los nombres.",
        )

    @admin.action(description="📊 Exportar catálogo a CSV")
    def export_catalog(self, request, queryset):
        """Exportar productos a CSV"""
        import csv
        from django.http import HttpResponse
        from django.utils import timezone

        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = (
            f'attachment; filename="catalogo_{timezone.now().strftime("%Y%m%d")}.csv"'
        )
        response.write("\ufeff")  # BOM para Excel

        writer = csv.writer(response)
        writer.writerow(
            [
                "ID",
                "Nombre",
                "Tipo",
                "Uso",
                "Estrategia",
                "Alcance",
                "Precio Base",
                "Temporada",
                "Activo",
                "Configurado",
                "Órdenes",
            ]
        )

        for product in queryset:
            from orders.models import OrderItem

            order_count = OrderItem.objects.filter(product=product).count()

            writer.writerow(
                [
                    product.id,
                    product.name,
                    product.get_product_type_display(),
                    product.get_usage_type_display(),
                    product.get_size_strategy_display(),
                    product.get_scope_display(),
                    product.base_price,
                    product.season.name,
                    "Sí" if product.is_active else "No",
                    "Sí" if product.is_configured else "No",
                    order_count,
                ]
            )

        return response


# ============================================================
# PRODUCT MEASUREMENT FIELD ADMIN
# ============================================================
@admin.register(ProductMeasurementField)
class ProductMeasurementFieldAdmin(admin.ModelAdmin):
    list_display = (
        "product",
        "field_name_display",
        "required_badge",
        "field_type_info",
    )
    list_filter = ("required", "field__field_type")
    search_fields = ("product__name", "field__name")
    raw_id_fields = ("product", "field")

    def field_name_display(self, obj):
        return (
            f"{obj.field.name} ({obj.field.unit})" if obj.field.unit else obj.field.name
        )

    field_name_display.short_description = "Campo"
    field_name_display.admin_order_field = "field__name"

    def required_badge(self, obj):
        if obj.required:
            return format_html(
                '<span style="background: #dc3545; color: white; padding: 2px 8px; '
                'border-radius: 3px; font-size: 10px; font-weight: bold;">* REQUERIDO</span>'
            )
        return format_html(
            '<span style="background: #6c757d; color: white; padding: 2px 8px; '
            'border-radius: 3px; font-size: 10px;">Opcional</span>'
        )

    required_badge.short_description = "Estado"

    def field_type_info(self, obj):
        return format_html(
            '<code style="background: #f0f0f0; padding: 2px 6px; border-radius: 3px;">{}</code>',
            obj.field.get_field_type_display(),
        )

    field_type_info.short_description = "Tipo de dato"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("product", "field")


# ============================================================
# PRODUCT SIZE VARIANT ADMIN
# ============================================================
@admin.register(ProductSizeVariant)
class ProductSizeVariantAdmin(admin.ModelAdmin):
    list_display = (
        "product",
        "size_badge",
        "additional_price_display",
        "final_price_display",
        "usage_count",
    )
    list_filter = ("size",)
    search_fields = ("product__name", "size")
    raw_id_fields = ("product",)
    ordering = ("product", "size")

    def size_badge(self, obj):
        return format_html(
            '<span style="background: #007bff; color: white; padding: 4px 12px; '
            'border-radius: 3px; font-weight: bold; font-size: 13px;">{}</span>',
            obj.size,
        )

    size_badge.short_description = "Talla"
    size_badge.admin_order_field = "size"

    def additional_price_display(self, obj):
        value = obj.additional_price or Decimal("0.00")
        value_str = format_currency(value)

        if value > 0:
            return format_html(
                '<span style="color: #28a745; font-weight: bold;">+${}</span>',
                value_str,
            )

        return format_html(
            '<span style="color: #999;">${}</span>',
            value_str,
        )

    additional_price_display.short_description = "Precio adicional"
    additional_price_display.admin_order_field = "additional_price"

    def final_price_display(self, obj):
        base = obj.product.base_price or Decimal("0.00")
        additional = obj.additional_price or Decimal("0.00")

        total = base + additional
        total_str = format_currency(total)

        return format_html(
            '<strong style="color: #007bff; font-size: 14px;">${}</strong>',
            total_str,
        )

    final_price_display.short_description = "Precio final"

    def usage_count(self, obj):
        """Número de veces que se ha usado esta talla"""
        from orders.models import OrderItem

        count = OrderItem.objects.filter(size_variant=obj).count()

        if count == 0:
            return format_html('<span style="color: #999;">Sin uso</span>')

        return format_html(
            '<strong>{}</strong> <span style="color: #666;">órdenes</span>', count
        )

    usage_count.short_description = "Uso"
    usage_count.admin_order_field = "usage_count_annotated"

    def get_queryset(self, request):

        return (
            super()
            .get_queryset(request)
            .select_related("product")
            .annotate(usage_count_annotated=Count("orderitem", distinct=True))
        )

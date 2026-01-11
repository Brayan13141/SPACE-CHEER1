from django.contrib import admin
from .models import MeasurementField, MeasurementValue


@admin.register(MeasurementField)
class MeasurementFieldAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "field_type", "unit", "required", "order")
    list_filter = ("field_type", "required")
    search_fields = ("name", "slug")
    ordering = ("order", "name")
    prepopulated_fields = {"slug": ("name",)}

    # Evita errores comunes donde alguien cambia el slug y rompe las medidas existentes
    def get_readonly_fields(self, request, obj=None):
        if obj:  # si ya existe
            return ("slug",)
        return ()


@admin.register(MeasurementValue)
class MeasurementValueAdmin(admin.ModelAdmin):
    list_display = ("user", "field", "value", "updated_at")
    list_filter = ("field",)
    search_fields = ("user__username", "field__name", "value")
    ordering = ("field__order",)

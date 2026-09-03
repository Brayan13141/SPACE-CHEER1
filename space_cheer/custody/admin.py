# custody/admin.py

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse

from custody.models import Guardianship


# ============================================================
# VÍNCULO DE TUTELA
# ============================================================
class GuardianshipInline(admin.TabularInline):
    """Los tutores de un atleta, desde la ficha del atleta."""

    model = Guardianship
    fk_name = "athlete"
    extra = 0
    fields = ("guardian", "relation", "legal_document", "verified_by", "verified_at")
    readonly_fields = ("verified_by", "verified_at")
    raw_id_fields = ("guardian",)


@admin.register(Guardianship)
class GuardianshipAdmin(admin.ModelAdmin):
    list_display = (
        "athlete_link", "guardian_link", "relation_badge", "verification_badge",
    )
    list_filter = ("relation",)
    search_fields = (
        "athlete__username",
        "athlete__first_name",
        "athlete__last_name",
        "guardian__username",
        "guardian__email",
        "guardian__first_name",
        "guardian__last_name",
    )
    raw_id_fields = ("athlete", "guardian", "verified_by", "created_by")
    readonly_fields = ("created_at",)

    def _user_link(self, user):
        url = reverse("admin:accounts_user_change", args=[user.id])
        return format_html(
            '<a href="{}">{}</a>', url, user.get_full_name() or user.username,
        )

    def athlete_link(self, obj):
        return self._user_link(obj.athlete)

    athlete_link.short_description = "Atleta"
    athlete_link.admin_order_field = "athlete__last_name"

    def guardian_link(self, obj):
        return self._user_link(obj.guardian)

    guardian_link.short_description = "Tutor"
    guardian_link.admin_order_field = "guardian__last_name"

    def relation_badge(self, obj):
        colors = {
            "PADRE": "#28a745",
            "TUTOR": "#007bff",
            "ACOMP": "#6c757d",
        }
        color = colors.get(obj.relation, "#6c757d")
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 8px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color,
            obj.get_relation_display(),
        )

    relation_badge.short_description = "Relación"

    def verification_badge(self, obj):
        if not obj.requires_proof:
            return format_html('<span style="color: #999;">no aplica</span>')
        if obj.is_verified:
            return format_html(
                '<span style="color: #28a745; font-weight: bold;">verificado</span>'
            )
        return format_html(
            '<span style="color: #dc3545; font-weight: bold;">sin verificar</span>'
        )

    verification_badge.short_description = "Respaldo"

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("athlete", "guardian", "verified_by")
        )

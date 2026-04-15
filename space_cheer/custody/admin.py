# custody/admin.py

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse

from custody.models import GuardianProfile


# ============================================================
# GUARDIAN PROFILE INLINE (para usar en accounts admin)
# ============================================================
class GuardianProfileInline(admin.StackedInline):
    model = GuardianProfile
    can_delete = False
    fields = ("relation",)

    def has_add_permission(self, request, obj=None):
        return False


# ============================================================
# GUARDIAN PROFILE ADMIN
# ============================================================
@admin.register(GuardianProfile)
class GuardianProfileAdmin(admin.ModelAdmin):
    list_display = ("user_link", "relation_badge", "athletes_count")
    list_filter = ("relation",)
    search_fields = (
        "user__username",
        "user__email",
        "user__first_name",
        "user__last_name",
    )
    raw_id_fields = ("user",)

    def user_link(self, obj):
        url = reverse("admin:accounts_user_change", args=[obj.user.id])
        return format_html(
            '<a href="{}">{}</a>',
            url,
            obj.user.get_full_name() or obj.user.username,
        )

    user_link.short_description = "Guardian"
    user_link.admin_order_field = "user__last_name"

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

    def athletes_count(self, obj):
        count = obj.user.athletes_under_guardian.count()
        if count == 0:
            return format_html('<span style="color: #999;">0 atletas</span>')
        return format_html(
            '<span style="color: #28a745; font-weight: bold;">{} atleta(s)</span>',
            count,
        )

    athletes_count.short_description = "Atletas a cargo"

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("user")
            .prefetch_related("user__athletes_under_guardian")
        )

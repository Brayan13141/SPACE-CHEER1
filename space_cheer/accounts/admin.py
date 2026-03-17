# accounts/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (
    User,
    Role,
    UserOwnership,
    AthleteProfile,
    CoachProfile,
    StaffProfile,
)


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "requires_curp",
        "is_athlete_type",
        "is_coach_type",
        "is_staff_type",
        "allow_dashboard_access",
    )
    list_editable = (
        "requires_curp",
        "is_athlete_type",
        "is_coach_type",
        "is_staff_type",
        "allow_dashboard_access",
    )
    ordering = ("name",)


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = (
        "username",
        "email",
        "get_full_name",
        "get_roles",
        "is_active",
        "is_staff",
        "date_joined",
    )
    list_filter = ("is_active", "is_staff", "roles")
    search_fields = ("username", "email", "first_name", "last_name")
    ordering = ("-date_joined",)

    # Agregar roles al formulario de edición
    fieldsets = UserAdmin.fieldsets + (
        (
            "SpaceCheer",
            {
                "fields": (
                    "roles",
                    "phone",
                    "birth_date",
                    "gender",
                    "curp",
                    "profile_completed",
                    "terms_accepted",
                    "privacy_accepted",
                    "foto_perfil",
                )
            },
        ),
    )

    filter_horizontal = ("roles", "groups", "user_permissions")

    @admin.display(description="Roles")
    def get_roles(self, obj):
        return ", ".join(obj.roles.values_list("name", flat=True)) or "—"


@admin.register(UserOwnership)
class UserOwnershipAdmin(admin.ModelAdmin):
    list_display = ("owner", "user", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("owner__username", "user__username", "owner__email", "user__email")
    raw_id_fields = ("owner", "user")

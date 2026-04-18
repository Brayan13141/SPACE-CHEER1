# accounts/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.db.models import Count, Q, Prefetch
from django.urls import reverse
from django.utils import timezone
from .models import (
    User,
    Role,
    UserOwnership,
    UserAddress,
    AthleteProfile,
    AthleteMedicalInfo,
    CoachProfile,
    StaffProfile,
)


# ============================================================
# ROLE ADMIN
# ============================================================
@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "type_badges",
        "requires_curp_badge",
        "dashboard_access_badge",
        "user_count",
    )
    list_filter = (
        "requires_curp",
        "is_staff_type",
        "is_athlete_type",
        "is_coach_type",
        "allow_dashboard_access",
    )
    search_fields = ("name",)
    ordering = ("name",)

    fieldsets = (
        ("Información Básica", {"fields": ("name",)}),
        (
            "Configuración",
            {
                "fields": (
                    "requires_curp",
                    "allow_dashboard_access",
                )
            },
        ),
        (
            "Tipo de Rol",
            {
                "fields": (
                    "is_staff_type",
                    "is_athlete_type",
                    "is_coach_type",
                ),
                "description": "Define el tipo de rol para la jerarquía del sistema",
            },
        ),
    )

    def type_badges(self, obj):
        """Badges visuales del tipo de rol"""
        badges = []

        if obj.is_staff_type:
            badges.append(
                '<span style="background: #6c757d; color: white; padding: 2px 6px; border-radius: 3px; font-size: 10px; margin-right: 3px;">👔 STAFF</span>'
            )

        if obj.is_athlete_type:
            badges.append(
                '<span style="background: #007bff; color: white; padding: 2px 6px; border-radius: 3px; font-size: 10px; margin-right: 3px;">🏃 ATLETA</span>'
            )

        if obj.is_coach_type:
            badges.append(
                '<span style="background: #28a745; color: white; padding: 2px 6px; border-radius: 3px; font-size: 10px; margin-right: 3px;">🎓 COACH</span>'
            )

        if not badges:
            return '<span style="color: #999;">Sin tipo definido</span>'

        return format_html("".join(badges))

    type_badges.short_description = "Tipos"

    def requires_curp_badge(self, obj):
        if obj.requires_curp:
            return format_html(
                '<span style="color: #dc3545; font-weight: bold;">✓ Requiere CURP</span>'
            )
        return format_html('<span style="color: #999;">○</span>')

    requires_curp_badge.short_description = "CURP"

    def dashboard_access_badge(self, obj):
        if obj.allow_dashboard_access:
            return format_html('<span style="color: #28a745;">✓ Dashboard</span>')
        return format_html('<span style="color: #999;">✗ Sin acceso</span>')

    dashboard_access_badge.short_description = "Acceso"

    def user_count(self, obj):
        """Número de usuarios con este rol"""
        count = obj.users.count()
        if count == 0:
            return format_html('<span style="color: #999;">0 usuarios</span>')

        url = reverse("admin:accounts_user_changelist") + f"?roles__id__exact={obj.id}"
        return format_html('<a href="{}">{} usuarios</a>', url, count)

    user_count.short_description = "Usuarios"
    user_count.admin_order_field = "user_count_annotated"

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(user_count_annotated=Count("users", distinct=True))
        )


# ============================================================
# USER ADDRESS INLINE
# ============================================================
class UserAddressInline(admin.TabularInline):
    model = UserAddress
    extra = 0
    fields = ("label", "address", "city", "zip_code", "is_default")

    def get_queryset(self, request):
        return super().get_queryset(request).order_by("-is_default", "label")


# ============================================================
# ATHLETE MEDICAL INFO INLINE
# ============================================================
class AthleteMedicalInfoInline(admin.StackedInline):
    model = AthleteMedicalInfo
    can_delete = False
    fields = (
        ("allergies", "medications"),
        "medical_notes",
        ("has_insurance", "insurance_policy_number"),
    )

    def has_add_permission(self, request, obj=None):
        # No permitir crear manualmente, se crea automáticamente con signal
        return False


# ============================================================
# ATHLETE PROFILE INLINE
# ============================================================
class AthleteProfileInline(admin.StackedInline):
    model = AthleteProfile
    can_delete = False
    fields = (
        ("emergency_contact", "emergency_phone"),
        "is_active_competitor",
        "guardian",
    )
    raw_id_fields = ("guardian",)

    def has_add_permission(self, request, obj=None):
        return False


# ============================================================
# COACH PROFILE INLINE
# ============================================================
class CoachProfileInline(admin.StackedInline):
    model = CoachProfile
    can_delete = False
    fields = ("experience_years", "certifications")

    def has_add_permission(self, request, obj=None):
        return False


# ============================================================
# STAFF PROFILE INLINE
# ============================================================
class StaffProfileInline(admin.StackedInline):
    model = StaffProfile
    can_delete = False
    fields = ("role_description", "staff_id")

    def has_add_permission(self, request, obj=None):
        return False


# ============================================================
# USER OWNERSHIP INLINE (para mostrar en User)
# ============================================================
class OwnedUsersInline(admin.TabularInline):
    model = UserOwnership
    fk_name = "owner"
    extra = 0
    fields = ("user", "is_active", "created_at", "deactivated_at")
    readonly_fields = ("created_at", "deactivated_at")
    raw_id_fields = ("user",)
    verbose_name = "Usuario bajo propiedad"
    verbose_name_plural = "Usuarios bajo propiedad (como coach)"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user")


# ============================================================
# USER ADMIN - EL MONSTRUO
# ============================================================
@admin.register(User)
class CustomUserAdmin(BaseUserAdmin):
    list_display = (
        "username",
        "email_display",
        "full_name_display",
        "role_badges",
        "phone_display",
        "age_display",
        "profile_status",
        "is_active",
        "date_joined",
    )
    list_filter = (
        "is_active",
        "is_staff",
        "is_superuser",
        "roles",
        "privacy_accepted",
        "terms_accepted",
        "profile_completed",
        ("date_joined", admin.DateFieldListFilter),
    )
    search_fields = (
        "username",
        "email",
        "first_name",
        "last_name",
        "phone",
        "curp",
    )
    ordering = ("-date_joined",)
    filter_horizontal = ("roles", "groups", "user_permissions")
    date_hierarchy = "date_joined"

    # Inlines dinámicos según roles
    inlines = [
        UserAddressInline,
        OwnedUsersInline,
    ]

    # Fieldsets reorganizados
    fieldsets = (
        ("Credenciales", {"fields": ("username", "password")}),
        (
            "Información Personal",
            {
                "fields": (
                    ("first_name", "last_name"),
                    "email",
                    ("phone", "curp"),
                    ("birth_date", "gender"),
                    "foto_perfil",
                )
            },
        ),
        (
            "Roles y Permisos",
            {
                "fields": (
                    "roles",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Consentimientos y Estado",
            {
                "fields": (
                    "is_active",
                    ("privacy_accepted", "terms_accepted"),
                    "profile_completed",
                )
            },
        ),
        (
            "Fechas",
            {"fields": (("date_joined", "last_login"),), "classes": ("collapse",)},
        ),
    )

    # Fieldsets para creación de usuario
    add_fieldsets = (
        (
            "Credenciales",
            {
                "classes": ("wide",),
                "fields": ("username", "password1", "password2"),
            },
        ),
        (
            "Información Básica",
            {"fields": ("email", "first_name", "last_name", "roles")},
        ),
    )

    # Readonly fields
    readonly_fields = ("date_joined", "last_login")

    # Acciones bulk
    actions = [
        "activate_users",
        "deactivate_users",
        "mark_profile_completed",
        "export_users_csv",
    ]

    # ============ MÉTODOS DE DISPLAY ============

    def email_display(self, obj):
        if obj.email:
            return format_html('<a href="mailto:{}">{}</a>', obj.email, obj.email)
        return format_html('<span style="color: #999;">Sin email</span>')

    email_display.short_description = "Email"
    email_display.admin_order_field = "email"

    def full_name_display(self, obj):
        full_name = obj.get_full_name()
        if full_name:
            return full_name
        return format_html('<span style="color: #999;">Sin nombre</span>')

    full_name_display.short_description = "Nombre completo"
    full_name_display.admin_order_field = "last_name"

    def role_badges(self, obj):
        """Badges de roles del usuario"""
        roles = obj.roles.all()

        if not roles:
            return format_html('<span style="color: #999;">Sin roles</span>')

        badges = []
        colors = {
            "ADMIN": "#dc3545",
            "HEADCOACH": "#28a745",
            "COACH": "#17a2b8",
            "ATHLETE": "#007bff",
            "STAFF": "#6c757d",
            "ACOMPANANTE": "#ffc107",
        }

        for role in roles:
            color = colors.get(role.name, "#6c757d")
            badges.append(
                f'<span style="background: {color}; color: white; padding: 2px 6px; '
                f'border-radius: 3px; font-size: 10px; margin-right: 3px;">{role.name}</span>'
            )

        return format_html("".join(badges))

    role_badges.short_description = "Roles"

    def phone_display(self, obj):
        if obj.phone:
            return format_html(
                '<span style="font-family: monospace;">{}</span>', obj.phone
            )
        return format_html('<span style="color: #999;">-</span>')

    phone_display.short_description = "Teléfono"

    def age_display(self, obj):
        """Mostrar edad y si es menor de edad"""
        if not obj.birth_date:
            return format_html('<span style="color: #999;">-</span>')

        today = timezone.now().date()
        age = (
            today.year
            - obj.birth_date.year
            - ((today.month, today.day) < (obj.birth_date.month, obj.birth_date.day))
        )

        if obj.is_minor:
            return format_html(
                '<span style="color: #ffc107; font-weight: bold;">{} años (menor)</span>',
                age,
            )
        return f"{age} años"

    age_display.short_description = "Edad"

    def profile_status(self, obj):
        """Estado del perfil completo"""
        if obj.profile_completed:
            return format_html('<span style="color: #28a745;">✓ Completo</span>')

        issues = []
        if not obj.first_name or not obj.last_name:
            issues.append("nombre")
        if not obj.email:
            issues.append("email")
        if not obj.roles.exists():
            issues.append("rol")

        if issues:
            return format_html(
                '<span style="color: #dc3545;" title="Falta: {}">✗ Incompleto</span>',
                ", ".join(issues),
            )
        return format_html('<span style="color: #ffc107;">⚠ Sin marcar</span>')

    profile_status.short_description = "Perfil"

    def get_queryset(self, request):
        """Optimización brutal de queries"""
        return (
            super()
            .get_queryset(request)
            .prefetch_related(
                "roles",
                "addresses",
            )
            .select_related(
                "athleteprofile",
                "coachprofile",
                "staffprofile",
                "guardianprofile",
            )
        )

    def get_inlines(self, request, obj=None):
        """Inlines dinámicos según roles del usuario"""
        inlines = [UserAddressInline, OwnedUsersInline]

        if obj:
            # Agregar inline de perfil según rol
            if obj.roles.filter(name="ATHLETE").exists():
                if hasattr(obj, "athleteprofile"):
                    inlines.insert(0, AthleteProfileInline)
                    if hasattr(obj.athleteprofile, "athletemedicalinfo"):
                        inlines.insert(1, AthleteMedicalInfoInline)

            if obj.roles.filter(name__in=["COACH", "HEADCOACH"]).exists():
                if hasattr(obj, "coachprofile"):
                    inlines.insert(0, CoachProfileInline)

            if obj.roles.filter(name="STAFF").exists():
                if hasattr(obj, "staffprofile"):
                    inlines.insert(0, StaffProfileInline)

            if obj.roles.filter(name__in=["GUARDIAN", "ACOMPANANTE"]).exists():
                if hasattr(obj, "guardianprofile"):
                    from custody.admin import GuardianProfileInline
                    inlines.insert(0, GuardianProfileInline)

        return inlines

    # ============ ACCIONES BULK ============

    @admin.action(description="✓ Activar usuarios seleccionados")
    def activate_users(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} usuarios activados.")

    @admin.action(description="✗ Desactivar usuarios seleccionados")
    def deactivate_users(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} usuarios desactivados.")

    @admin.action(description="📋 Marcar perfil como completado")
    def mark_profile_completed(self, request, queryset):
        updated = queryset.update(profile_completed=True)
        self.message_user(request, f"{updated} perfiles marcados como completados.")

    @admin.action(description="📊 Exportar usuarios a CSV")
    def export_users_csv(self, request, queryset):
        import csv
        from django.http import HttpResponse

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            f'attachment; filename="usuarios_{timezone.now().strftime("%Y%m%d")}.csv"'
        )

        writer = csv.writer(response)
        writer.writerow(
            [
                "Username",
                "Email",
                "Nombre",
                "Apellido",
                "Teléfono",
                "CURP",
                "Roles",
                "Activo",
                "Registrado",
            ]
        )

        for user in queryset.prefetch_related("roles"):
            roles = ", ".join(user.roles.values_list("name", flat=True))
            writer.writerow(
                [
                    user.username,
                    user.email,
                    user.first_name,
                    user.last_name,
                    user.phone or "",
                    user.curp or "",
                    roles,
                    "Sí" if user.is_active else "No",
                    user.date_joined.strftime("%Y-%m-%d"),
                ]
            )

        return response


# ============================================================
# USER OWNERSHIP ADMIN
# ============================================================
@admin.register(UserOwnership)
class UserOwnershipAdmin(admin.ModelAdmin):
    list_display = (
        "owner_display",
        "user_display",
        "status_badge",
        "created_at",
        "duration_display",
    )
    list_filter = (
        "is_active",
        ("created_at", admin.DateFieldListFilter),
        ("deactivated_at", admin.DateFieldListFilter),
    )
    search_fields = (
        "owner__username",
        "owner__email",
        "owner__first_name",
        "owner__last_name",
        "user__username",
        "user__email",
        "user__first_name",
        "user__last_name",
    )
    raw_id_fields = ("owner", "user")
    readonly_fields = ("created_at", "deactivated_at")
    date_hierarchy = "created_at"

    fieldsets = (
        ("Relación", {"fields": ("owner", "user")}),
        ("Estado", {"fields": ("is_active",)}),
        (
            "Fechas",
            {"fields": ("created_at", "deactivated_at"), "classes": ("collapse",)},
        ),
    )

    actions = ["activate_ownerships", "deactivate_ownerships"]

    def owner_display(self, obj):
        url = reverse("admin:accounts_user_change", args=[obj.owner.id])
        return format_html(
            '<a href="{}">{}</a>', url, obj.owner.get_full_name() or obj.owner.username
        )

    owner_display.short_description = "Coach (dueño)"
    owner_display.admin_order_field = "owner__last_name"

    def user_display(self, obj):
        url = reverse("admin:accounts_user_change", args=[obj.user.id])
        return format_html(
            '<a href="{}">{}</a>', url, obj.user.get_full_name() or obj.user.username
        )

    user_display.short_description = "Usuario"
    user_display.admin_order_field = "user__last_name"

    def status_badge(self, obj):
        if obj.is_active:
            return format_html(
                '<span style="background: #28a745; color: white; padding: 3px 8px; '
                'border-radius: 3px; font-size: 11px;">✓ Activo</span>'
            )
        return format_html(
            '<span style="background: #6c757d; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-size: 11px;">○ Inactivo</span>'
        )

    status_badge.short_description = "Estado"

    def duration_display(self, obj):
        """Duración de la relación"""
        start = obj.created_at
        end = obj.deactivated_at or timezone.now()
        duration = end - start

        days = duration.days
        if days < 30:
            return f"{days} días"
        elif days < 365:
            return f"{days // 30} meses"
        return f"{days // 365} años"

    duration_display.short_description = "Duración"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("owner", "user")

    @admin.action(description="✓ Activar relaciones seleccionadas")
    def activate_ownerships(self, request, queryset):
        updated = queryset.update(is_active=True, deactivated_at=None)
        self.message_user(request, f"{updated} relaciones activadas.")

    @admin.action(description="✗ Desactivar relaciones seleccionadas")
    def deactivate_ownerships(self, request, queryset):
        updated = queryset.update(is_active=False, deactivated_at=timezone.now())
        self.message_user(request, f"{updated} relaciones desactivadas.")


# ============================================================
# USER ADDRESS ADMIN
# ============================================================
@admin.register(UserAddress)
class UserAddressAdmin(admin.ModelAdmin):
    list_display = (
        "user_link",
        "label",
        "address_display",
        "city",
        "zip_code",
        "default_badge",
    )
    list_filter = ("is_default", "city")
    search_fields = (
        "user__username",
        "user__email",
        "label",
        "address",
        "city",
        "zip_code",
    )
    raw_id_fields = ("user",)

    fieldsets = (
        ("Usuario", {"fields": ("user",)}),
        (
            "Dirección",
            {
                "fields": (
                    "label",
                    "address",
                    ("city", "zip_code"),
                    "is_default",
                )
            },
        ),
    )

    def user_link(self, obj):
        url = reverse("admin:accounts_user_change", args=[obj.user.id])
        return format_html(
            '<a href="{}">{}</a>', url, obj.user.get_full_name() or obj.user.username
        )

    user_link.short_description = "Usuario"
    user_link.admin_order_field = "user__last_name"

    def address_display(self, obj):
        return obj.address[:50] + "..." if len(obj.address) > 50 else obj.address

    address_display.short_description = "Dirección"

    def default_badge(self, obj):
        if obj.is_default:
            return format_html(
                '<span style="color: #28a745; font-weight: bold;">★ Predeterminada</span>'
            )
        return format_html('<span style="color: #999;">○</span>')

    default_badge.short_description = "Predeterminada"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user")

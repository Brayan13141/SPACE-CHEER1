# teams/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Q
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import Team, TeamCategory, UserTeamMembership, TeamSong


# ============================================================
# TEAM CATEGORY ADMIN
# ============================================================
@admin.register(TeamCategory)
class TeamCategoryAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "level",
        "team_count",
        "song_count",
        "description_preview",
    )
    list_filter = ("level",)
    search_fields = ("name", "description")
    ordering = ("level", "name")

    # Fieldsets para organización visual
    fieldsets = (
        ("Información Básica", {"fields": ("name", "level")}),
        ("Detalles", {"fields": ("description",), "classes": ("collapse",)}),
    )

    def team_count(self, obj):
        """Número de equipos en esta categoría"""
        count = obj.team_set.count()
        if count == 0:
            return format_html('<span style="color: #999;">0</span>')
        url = reverse("admin:teams_team_changelist") + f"?category__id__exact={obj.id}"
        return format_html('<a href="{}">{} equipos</a>', url, count)

    team_count.short_description = "Equipos"
    team_count.admin_order_field = "team_count_annotated"

    def song_count(self, obj):
        """Canciones asociadas a esta categoría"""
        return obj.songs.count()

    song_count.short_description = "Canciones"

    def description_preview(self, obj):
        """Preview de descripción truncada"""
        if obj.description:
            return (
                obj.description[:50] + "..."
                if len(obj.description) > 50
                else obj.description
            )
        return "-"

    description_preview.short_description = "Descripción"

    def get_queryset(self, request):
        """Optimizar queries con anotaciones"""
        qs = super().get_queryset(request)
        return qs.annotate(team_count_annotated=Count("team", distinct=True))


# ============================================================
# TEAM MEMBERSHIP INLINE
# ============================================================
class TeamMembershipInline(admin.TabularInline):
    model = UserTeamMembership
    extra = 0
    fields = (
        "user",
        "role_in_team",
        "status",
        "is_active",
        "start_date",
        "end_date",
    )
    raw_id_fields = ("user",)
    readonly_fields = ("date_joined",)

    def get_queryset(self, request):
        """Optimizar con select_related"""
        return super().get_queryset(request).select_related("user")


# ============================================================
# TEAM SONG INLINE
# ============================================================
class TeamSongInline(admin.TabularInline):
    model = TeamSong
    extra = 1
    fields = ("name", "audio", "category", "order", "is_active")
    ordering = ("order",)


# ============================================================
# TEAM ADMIN
# ============================================================
@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "coach_link",
        "category",
        "city",
        "member_count",
        "active_status",
        "join_code_display",
        "created_at",
    )
    list_filter = (
        "is_active",
        "category",
        "city",
        "created_at",
    )
    search_fields = (
        "name",
        "coach__username",
        "coach__email",
        "coach__first_name",
        "coach__last_name",
        "city",
        "join_code",
    )
    raw_id_fields = ("coach",)
    readonly_fields = (
        "join_code",
        "created_at",
        "member_summary",
        "order_count",
    )
    ordering = ("-created_at",)

    # Inlines
    inlines = [TeamMembershipInline, TeamSongInline]

    # Fieldsets
    fieldsets = (
        ("Información Básica", {"fields": ("name", "coach", "category")}),
        ("Ubicación", {"fields": ("address", "city", "phone")}),
        ("Multimedia", {"fields": ("logo",)}),
        ("Estado y Acceso", {"fields": ("is_active", "join_code")}),
        (
            "Estadísticas",
            {
                "fields": ("member_summary", "order_count", "created_at"),
                "classes": ("collapse",),
            },
        ),
    )

    # Acciones personalizadas
    actions = ["activate_teams", "deactivate_teams", "regenerate_join_codes"]

    def coach_link(self, obj):
        """Link al coach en admin"""
        url = reverse("admin:accounts_user_change", args=[obj.coach.id])
        return format_html(
            '<a href="{}">{}</a>', url, obj.coach.get_full_name() or obj.coach.username
        )

    coach_link.short_description = "Coach"
    coach_link.admin_order_field = "coach__last_name"

    def member_count(self, obj):
        """Número de miembros activos"""
        active = obj.memberships.filter(is_active=True, status="accepted").count()
        total = obj.memberships.count()

        if active == 0:
            color = "#999"
        elif active == total:
            color = "#28a745"
        else:
            color = "#ffc107"

        return format_html(
            '<span style="color: {}; font-weight: bold;">{}/{}</span>',
            color,
            active,
            total,
        )

    member_count.short_description = "Miembros (activos/total)"

    def active_status(self, obj):
        """Badge visual del estado"""
        if obj.is_active:
            return format_html(
                '<span style="background: #28a745; color: white; padding: 3px 10px; border-radius: 3px;">✓ Activo</span>'
            )
        return format_html(
            '<span style="background: #dc3545; color: white; padding: 3px 10px; border-radius: 3px;">✗ Inactivo</span>'
        )

    active_status.short_description = "Estado"

    def join_code_display(self, obj):
        """Mostrar código con estilo"""
        return format_html(
            '<code style="background: #f0f0f0; padding: 2px 6px; border-radius: 3px; font-family: monospace;">{}</code>',
            obj.join_code,
        )

    join_code_display.short_description = "Código de acceso"

    def member_summary(self, obj):
        """Resumen detallado de miembros"""
        memberships = obj.memberships.select_related("user")

        stats = {
            "atletas": memberships.filter(
                role_in_team="ATHLETE", is_active=True
            ).count(),
            "coaches": memberships.filter(role_in_team="COACH", is_active=True).count(),
            "staff": memberships.filter(role_in_team="STAFF", is_active=True).count(),
            "pending": memberships.filter(status="pending").count(),
            "inactive": memberships.filter(is_active=False).count(),
        }

        return format_html(
            """
            <div style="line-height: 1.8;">
                <strong>Atletas:</strong> {atletas}<br>
                <strong>Coaches:</strong> {coaches}<br>
                <strong>Staff:</strong> {staff}<br>
                <strong style="color: #ffc107;">Pendientes:</strong> {pending}<br>
                <strong style="color: #999;">Inactivos:</strong> {inactive}
            </div>
            """,
            **stats,
        )

    member_summary.short_description = "Resumen de miembros"

    def order_count(self, obj):
        """Número de órdenes del equipo"""
        from orders.models import Order

        count = Order.objects.filter(owner_team=obj).count()
        if count == 0:
            return "0 órdenes"
        url = (
            reverse("admin:orders_order_changelist")
            + f"?owner_team__id__exact={obj.id}"
        )
        return format_html('<a href="{}">{} órdenes</a>', url, count)

    order_count.short_description = "Órdenes"

    def get_queryset(self, request):
        """Optimizar queries"""
        return (
            super()
            .get_queryset(request)
            .select_related("coach", "category")
            .prefetch_related("memberships")
        )

    # ============ ACCIONES BULK ============

    @admin.action(description="✓ Activar equipos seleccionados")
    def activate_teams(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} equipos activados correctamente.")

    @admin.action(description="✗ Desactivar equipos seleccionados")
    def deactivate_teams(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} equipos desactivados correctamente.")

    @admin.action(description="🔄 Regenerar códigos de acceso")
    def regenerate_join_codes(self, request, queryset):
        import secrets

        for team in queryset:
            team.join_code = secrets.token_hex(3).upper()
            team.save(update_fields=["join_code"])
        self.message_user(
            request, f"Códigos regenerados para {queryset.count()} equipos."
        )


# ============================================================
# USER TEAM MEMBERSHIP ADMIN
# ============================================================
@admin.register(UserTeamMembership)
class UserTeamMembershipAdmin(admin.ModelAdmin):
    list_display = (
        "user_link",
        "team_link",
        "role_badge",
        "status_badge",
        "active_period",
        "date_joined",
    )
    list_filter = (
        "role_in_team",
        "status",
        "is_active",
        ("date_joined", admin.DateFieldListFilter),
    )
    search_fields = (
        "user__username",
        "user__email",
        "user__first_name",
        "user__last_name",
        "team__name",
    )
    raw_id_fields = ("user", "team")
    readonly_fields = ("date_joined",)
    date_hierarchy = "date_joined"

    fieldsets = (
        ("Relación", {"fields": ("user", "team")}),
        ("Rol y Estado", {"fields": ("role_in_team", "status", "is_active")}),
        ("Fechas", {"fields": ("date_joined", "start_date", "end_date")}),
    )

    actions = ["accept_memberships", "reject_memberships", "deactivate_memberships"]

    def user_link(self, obj):
        url = reverse("admin:accounts_user_change", args=[obj.user.id])
        return format_html(
            '<a href="{}">{}</a>', url, obj.user.get_full_name() or obj.user.username
        )

    user_link.short_description = "Usuario"
    user_link.admin_order_field = "user__last_name"

    def team_link(self, obj):
        url = reverse("admin:teams_team_change", args=[obj.team.id])
        return format_html('<a href="{}">{}</a>', url, obj.team.name)

    team_link.short_description = "Equipo"
    team_link.admin_order_field = "team__name"

    def role_badge(self, obj):
        colors = {
            "ATHLETE": "#007bff",
            "COACH": "#28a745",
            "STAFF": "#ffc107",
        }
        color = colors.get(obj.role_in_team, "#6c757d")
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 8px; border-radius: 3px; font-size: 11px;">{}</span>',
            color,
            obj.get_role_in_team_display(),
        )

    role_badge.short_description = "Rol"

    def status_badge(self, obj):
        colors = {
            "pending": "#ffc107",
            "accepted": "#28a745",
            "rejected": "#dc3545",
            "inactive": "#6c757d",
        }
        icons = {
            "pending": "⏳",
            "accepted": "✓",
            "rejected": "✗",
            "inactive": "○",
        }
        color = colors.get(obj.status, "#6c757d")
        icon = icons.get(obj.status, "")
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 8px; border-radius: 3px; font-size: 11px;">{} {}</span>',
            color,
            icon,
            obj.get_status_display(),
        )

    status_badge.short_description = "Estado"

    def active_period(self, obj):
        if not obj.is_active:
            return format_html('<span style="color: #999;">Inactivo</span>')

        start = obj.start_date.strftime("%d/%m/%Y")
        end = obj.end_date.strftime("%d/%m/%Y") if obj.end_date else "Presente"
        return f"{start} → {end}"

    active_period.short_description = "Período activo"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user", "team")

    # ============ ACCIONES BULK ============

    @admin.action(description="✓ Aceptar membresías seleccionadas")
    def accept_memberships(self, request, queryset):
        for membership in queryset:
            membership.accept()
        self.message_user(request, f"{queryset.count()} membresías aceptadas.")

    @admin.action(description="✗ Rechazar membresías seleccionadas")
    def reject_memberships(self, request, queryset):
        for membership in queryset:
            membership.reject()
        self.message_user(request, f"{queryset.count()} membresías rechazadas.")

    @admin.action(description="○ Desactivar membresías seleccionadas")
    def deactivate_memberships(self, request, queryset):
        for membership in queryset:
            membership.deactivate()
        self.message_user(request, f"{queryset.count()} membresías desactivadas.")


# ============================================================
# TEAM SONG ADMIN
# ============================================================
@admin.register(TeamSong)
class TeamSongAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "team",
        "category",
        "order",
        "audio_player",
        "is_active",
    )
    list_filter = ("is_active", "team", "category")
    search_fields = ("name", "team__name")
    ordering = ("team", "category", "order")
    raw_id_fields = ("team",)

    def audio_player(self, obj):
        if obj.audio:
            return format_html(
                '<audio controls style="max-width: 200px;"><source src="{}" type="audio/mpeg"></audio>',
                obj.audio.url,
            )
        return "-"

    audio_player.short_description = "Reproducir"

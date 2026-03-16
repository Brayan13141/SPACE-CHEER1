# teams/admin.py
from django.contrib import admin
from .models import Team, TeamCategory, UserTeamMembership


@admin.register(TeamCategory)
class TeamCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "level", "description")
    ordering = ("level", "name")


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ("name", "coach", "city", "category", "is_active", "created_at")
    list_filter = ("is_active", "category")
    search_fields = ("name", "coach__username", "coach__email", "city")
    raw_id_fields = ("coach",)


@admin.register(UserTeamMembership)
class UserTeamMembershipAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "team",
        "role_in_team",
        "status",
        "is_active",
        "date_joined",
    )
    list_filter = ("role_in_team", "status", "is_active")
    search_fields = ("user__username", "user__email", "team__name")
    raw_id_fields = ("user", "team")

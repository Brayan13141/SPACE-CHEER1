# teams/urls.py

from django.urls import path
from . import views

app_name = "teams"

urlpatterns = [
    path("my-team/", views.athlete_team, name="athlete_team"),
    path("join/", views.join_by_code, name="join_by_code"),
    path("coach/", views.coach_teams, name="coach_teams"),
    # Rutas para la gestión de categorías
    path("categories/", views.manage_categories, name="manage_categories"),
    # Ruta para crear una nuevo equipo
    path("teams/", views.manage_teams, name="manage_teams"),
    path("<int:team_id>/regenerate-code/", views.regenerate_code, name="regenerate_code"),
    path(
        "manage_athletes/",
        views.manage_athletes,
        name="manage_athletes",
    ),
    path(
        "<int:team_id>/members/",
        views.manage_team_members,
        name="manage_team_members",
    ),
    path("requests/<int:membership_id>/accept/", views.accept_request, name="accept_request"),
    path("requests/<int:membership_id>/reject/", views.reject_request, name="reject_request"),
    path("members/<int:membership_id>/remove/", views.remove_member, name="remove_member"),
]

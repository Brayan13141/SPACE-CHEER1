# teams/urls.py

from django.urls import path
from . import views

urlpatterns = [
    # Rutas para la gestión de categorías
    path("categories/", views.manage_categories, name="manage_categories"),
    # Ruta para crear una nuevo equipo
    path("teams/", views.manage_teams, name="manage_teams"),
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
]

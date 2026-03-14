from django.urls import path
from . import views

urlpatterns = [
    path(
        "manage_athletes/<int:id>/edit_measures/",
        views.edit_athlete_measures,
        name="edit_athlete_measures",
    ),
    path(
        "members/",
        views.manage_owned_users,
        name="manage_owned_users",
    ),
    path(
        "members/remove/<int:ownership_id>/",
        views.remove_owned_user,
        name="remove_owned_user",
    ),
    # Ruta para crear un miembro del equipo
    path(
        "<int:team_id>/crew",
        views.create_team_crew_member,
        name="create_team_crew_member",
    ),
    # Rutas para la gestión de miembros del equipo
    # Rutas para modificar el rol o eliminar un miembro del equipo
    path(
        "membership/<int:membership_id>/role/",
        views.change_team_role,
        name="change_team_role",
    ),
    # Ruta para eliminar un miembro del equipo
    path(
        "membership/<int:membership_id>/remove/",
        views.remove_team_member,
        name="remove_team_member",
    ),
    # Ruta para agregar un miembro al equipo
    path(
        "<int:team_id>/members/add/",
        views.add_team_member,
        name="add_team_member",
    ),
]

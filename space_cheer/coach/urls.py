from django.urls import path
from . import views

urlpatterns = [
    # Medidas de atleta
    path(
        "manage_athletes/<int:id>/edit_measures/",
        views.edit_athlete_measures,
        name="edit_athlete_measures",
    ),
    # Usuarios propios (atletas + crew)
    path(
        "members/",  # ← quitado el / inicial
        views.manage_owned_users,
        name="manage_owned_users",
    ),
    path(
        "members/remove/<int:ownership_id>/",  # ← quitado el / inicial
        views.remove_owned_user,
        name="remove_owned_user",
    ),
    path(
        "members/edit/<int:ownership_id>/",
        views.edit_owned_user,
        name="edit_owned_user",
    ),
    # Crew
    path(
        "<int:team_id>/crew/addmember/",  # ← agregado / al final
        views.create_team_crew_member,
        name="create_team_crew_member",
    ),
    # Membresías
    path(
        "membership/<int:membership_id>/role/",
        views.change_team_role,
        name="change_team_role",
    ),
    path(
        "membership/<int:membership_id>/remove/",
        views.remove_team_member,
        name="remove_team_member",
    ),
    path(
        "<int:team_id>/members/add/",
        views.add_team_member,
        name="add_team_member",
    ),
]

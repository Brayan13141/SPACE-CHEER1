from django.urls import path
from . import views

app_name = "coach"

urlpatterns = [
    # =============================
    # ATHLETES
    # =============================
    path(
        "athletes/",
        views.manage_athletes,
        name="manage_athletes",
    ),
    path(
        "athletes/<int:id>/edit-measures/",
        views.edit_athlete_measures,
        name="edit_athlete_measures",
    ),
    # =============================
    # OWNED USERS (athletes + crew)
    # =============================
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
    path(
        "members/edit/<int:ownership_id>/",
        views.edit_owned_user,
        name="edit_owned_user",
    ),
    path(
        "members/reassign/<int:ownership_id>/",
        views.reassign_owned_user,
        name="reassign_owned_user",
    ),
    # =============================
    # TEAM MEMBERS
    # =============================
    path(
        "teams/<int:team_id>/members/add/",
        views.add_team_member,
        name="add_team_member",
    ),
    path(
        "teams/membership/<int:membership_id>/role/",
        views.change_team_role,
        name="change_team_role",
    ),
    path(
        "teams/membership/<int:membership_id>/remove/",
        views.remove_team_member,
        name="remove_team_member",
    ),
    # =============================
    # TEAM CREW
    # =============================
    path(
        "teams/<int:team_id>/crew/add/",
        views.create_team_crew_member,
        name="create_team_crew_member",
    ),
]

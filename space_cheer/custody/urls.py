# custody/urls.py
from django.urls import path
from custody import views

app_name = "guardian"

urlpatterns = [
    path("dashboard/", views.guardian_dashboard, name="dashboard"),
    path(
        "headcoach-dashboard/",
        views.headcoach_dashboard,
        name="headcoach_dashboard",
    ),
    path(
        "guardians/assign/<int:athlete_id>/",
        views.assign_guardian,
        name="assign_guardian",
    ),
    path(
        "guardians/remove/<int:athlete_id>/",
        views.remove_guardian,
        name="remove_guardian",
    ),
    path(
        "ownership/add/<int:user_id>/",
        views.ownership_add_user,
        name="ownership_add_user",
    ),
    path(
        "ownership/transfer/<int:ownership_id>/",
        views.ownership_transfer,
        name="ownership_transfer",
    ),
]

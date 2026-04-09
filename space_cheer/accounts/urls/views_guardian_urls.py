from django.urls import path
from accounts.views import views_guardian

app_name = "guardian"

urlpatterns = [
    path("dashboard/", views_guardian.guardian_dashboard, name="dashboard"),
    path(
        "headcoach-dashboard/",
        views_guardian.headcoach_dashboard,
        name="headcoach_dashboard",
    ),
    path(
        "guardians/assign/<int:athlete_id>/",
        views_guardian.assign_guardian,
        name="assign_guardian",
    ),
    path(
        "guardians/remove/<int:athlete_id>/",
        views_guardian.remove_guardian,
        name="remove_guardian",
    ),
    path(
        "guardians/minors-without/",
        views_guardian.minors_without_guardian_list,
        name="minors_without_guardian",
    ),
    path(
        "ownership/add/<int:user_id>/",
        views_guardian.ownership_add_user,
        name="ownership_add_user",
    ),
    path(
        "ownership/transfer/<int:ownership_id>/",
        views_guardian.ownership_transfer,
        name="ownership_transfer",
    ),
]

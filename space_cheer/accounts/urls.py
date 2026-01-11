from django.urls import path
from . import views

app_name = "accounts"

urlpatterns = [
    path("complete-profile/", views.profile_setup_view, name="profile_setup"),
    path("complete-profile/curp/", views.curp_verification, name="curp_verification"),
]

from django.urls import path
from . import views

app_name = "accounts"

urlpatterns = [
    # =========COMPLETAR PERFIL====================
    path("complete-profile/", views.profile_setup_view, name="profile_setup"),
    path("complete-profile/curp/", views.curp_verification, name="curp_verification"),
    # ==========DIRECCION===================
    path("", views.address_list, name="list_address"),
    path("create/", views.address_create, name="create_address"),
    path("<int:pk>/edit/", views.address_update, name="update_address"),
    path("<int:pk>/delete/", views.address_delete, name="delete_address"),
    # =============================
]

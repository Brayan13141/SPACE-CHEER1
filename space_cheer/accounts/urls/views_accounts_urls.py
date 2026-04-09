from django.urls import path
from accounts.views import views_accounts

app_name = "accounts"

urlpatterns = [
    # =============================
    # PROFILE
    # =============================
    path(
        "profile/complete/",
        views_accounts.profile_setup_view,
        name="profile_setup",
    ),
    path(
        "profile/curp/",
        views_accounts.curp_verification,
        name="curp_verification",
    ),
    # =============================
    # ADDRESS
    # =============================
    path(
        "addresses/",
        views_accounts.address_list,
        name="address_list",
    ),
    path(
        "addresses/create/",
        views_accounts.address_create,
        name="create_address",
    ),
    path(
        "addresses/<int:pk>/edit/",
        views_accounts.address_update,
        name="update_address",
    ),
    path(
        "addresses/<int:pk>/delete/",
        views_accounts.address_delete,
        name="delete_address",
    ),
]

# accounts/urls.py
from django.urls import path
from accounts.views import views_accounts, views_guardian, views_profile

app_name = "accounts"

urlpatterns = [
    # 1. ONBOARDING
    path("complete-profile/", views_accounts.profile_setup_view, name="profile_setup"),
    path(
        "complete-profile/curp/",
        views_accounts.curp_verification,
        name="curp_verification",
    ),
    # 2. PERFIL PROPIO
    path("profile/edit/", views_profile.profile_edit, name="profile_edit"),
    path(
        "profile/photo/upload/",
        views_profile.profile_photo_upload,
        name="profile_photo_upload",
    ),
    path(
        "profile/photo/delete/",
        views_profile.profile_photo_delete,
        name="profile_photo_delete",
    ),
    path("profile/settings/", views_profile.profile_settings, name="profile_settings"),
    path(
        "profile/deactivate/",
        views_profile.account_deactivate,
        name="account_deactivate",
    ),
    # 3. DIRECCIONES
    path("", views_accounts.address_list, name="list_address"),
    path("create/", views_accounts.address_create, name="create_address"),
    path("<int:pk>/edit/", views_accounts.address_update, name="update_address"),
    path("<int:pk>/delete/", views_accounts.address_delete, name="delete_address"),
    # 4. GUARDIAN
    path(
        "athletes/<int:athlete_id>/guardian/assign/",
        views_guardian.assign_guardian,
        name="assign_guardian",
    ),
    path(
        "athletes/<int:athlete_id>/guardian/remove/",
        views_guardian.remove_guardian,
        name="remove_guardian",
    ),
    path(
        "athletes/minors/no-guardian/",
        views_guardian.minors_without_guardian_list,
        name="minors_without_guardian",
    ),
    path(
        "guardian/dashboard/",
        views_profile.guardian_dashboard,
        name="guardian_dashboard",
    ),
    # 5. OWNERSHIP
    path(
        "ownership/<int:user_id>/add/",
        views_guardian.ownership_add_user,
        name="ownership_add",
    ),
    path(
        "ownership/<int:ownership_id>/transfer/",
        views_guardian.ownership_transfer,
        name="ownership_transfer",
    ),
    # 6. BÚSQUEDA + IMPORTACIÓN
    path("search/", views_profile.user_search_api, name="user_search"),
    path(
        "athletes/import/",
        views_profile.bulk_import_athletes,
        name="bulk_import_athletes",
    ),
    path(
        "athletes/import/template/",
        views_profile.bulk_import_template_download,
        name="bulk_import_template",
    ),
]

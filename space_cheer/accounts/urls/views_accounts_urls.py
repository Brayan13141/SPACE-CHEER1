# accounts/urls.py
from django.urls import path
from accounts.views import views_accounts, views_profile, views_notifications
from accounts.views.views_admin_approvals import headcoach_approvals

app_name = "accounts"

urlpatterns = [
    # 0. NOTIFICACIONES (gestión — excluye sociales, ver social:notifications)
    path("notificaciones/", views_notifications.notifications, name="notifications"),
    path(
        "notificaciones/<int:pk>/leer/",
        views_notifications.notification_read,
        name="notification_read",
    ),
    path(
        "notificaciones/leer-todas/",
        views_notifications.notifications_read_all,
        name="notifications_read_all",
    ),
    # 1. ONBOARDING
    path("complete-profile/", views_accounts.profile_setup_view, name="profile_setup"),
    path("coach/pending/", views_accounts.coach_pending_approval, name="coach_pending_approval"),
    path("coach/rejected/", views_accounts.coach_rejected, name="coach_rejected"),
    path("admin/headcoach-approvals/", headcoach_approvals, name="headcoach_approvals"),
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
    path("help/toggle/", views_profile.toggle_help, name="toggle_help"),
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
    # 4. BÚSQUEDA + IMPORTACIÓN
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

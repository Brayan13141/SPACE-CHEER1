from django.urls import path
from production.views import operario_views, admin_views, config_views

app_name = "production"

urlpatterns = [
    # Operario
    path("", operario_views.dashboard, name="dashboard"),
    path("task/<int:pk>/complete/", operario_views.task_complete, name="task_complete"),
    path("order/<int:pk>/design/", operario_views.order_design, name="order_design"),
    path("item/<int:pk>/measurements/", operario_views.item_measurements, name="item_measurements"),
    # Admin / Staff
    path("admin/", admin_views.admin_overview, name="admin_overview"),
    path("admin/job/<int:pk>/", admin_views.admin_job_detail, name="admin_job_detail"),
    path("admin/job/<int:pk>/toggle-urgent/", admin_views.toggle_urgent, name="toggle_urgent"),
    path("admin/task/<int:pk>/assign/", admin_views.assign_task, name="assign_task"),
    # Config (Admin only)
    path("config/stages/", config_views.manage_stages, name="manage_stages"),
    path("config/roles/", config_views.manage_roles, name="manage_roles"),
    path(
        "config/roles/<int:pk>/operarios/",
        config_views.manage_role_operarios,
        name="manage_role_operarios",
    ),
    path("config/operarios/", config_views.manage_operarios, name="manage_operarios"),
    path("config/operarios/<int:pk>/", config_views.operario_detail, name="operario_detail"),
]

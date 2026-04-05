from django.urls import path
from orders import views

app_name = "orders"

urlpatterns = [
    # ================================== Administrar orders ============================
    path("", views.order_list, name="manage_orders"),
    # ================================== Create order ============================``
    path("create/", views.create_order, name="create_order"),
    # ================================== Order details ============================
    path("<int:order_id>/", views.order_detail, name="detail_order"),
    # ================================== Order item details ============================
    path("items/<int:item_id>/", views.order_item_detail, name="order_item_detail"),
    # ================================== Edit order ============================
    path("<int:order_id>/edit/", views.order_edit, name="edit_order"),
    path(
        "items/<int:item_id>/delete/", views.order_item_delete, name="order_item_delete"
    ),
    # ================================== Contact info for order ============================
    path(
        "<int:order_id>/contact/",
        views.order_contact_info,
        name="contact_info_order",
    ),
    # ================================== Add item to order ============================
    path(
        "<int:order_id>/items/add/",
        views.order_add_product,
        name="add_item_product_order",
    ),
    # ================================== Import team athletes to item ============================
    path(
        "items/<int:item_id>/import-team/",
        views.import_team_athletes,
        name="item_import_team_athletes",
    ),
    # ================================== Add measurements to item ============================
    path(
        "items/athlete/<int:athlete_item_id>/measurements/",
        views.order_item_measurements,
        name="order_item_measurements",
    ),
    path(
        "items/athlete/<int:athlete_item_id>/measurements/add",
        views.item_measurements_order_add,
        name="item_measurements_order_add",
    ),
    # ================================== Transition order status ============================
    path(
        "<int:order_id>/transition/<str:to_status>/",
        views.transition_order,
        name="transition",
    ),
    # ==================================================================================
    # Lista de órdenes para admin
    # ==================================================================================
    path(
        "admin/orders/",
        views.admin_order_list,
        name="admin_order_list",
    ),
    # Detalle de orden para admin
    path(
        "admin/orders/<int:order_id>/",
        views.admin_order_detail,
        name="admin_order_detail",
    ),
    # Subir diseño a item
    path(
        "admin/orders/<int:order_id>/upload-design/",
        views.admin_upload_design,
        name="admin_upload_design",
    ),
    # Actualizar fechas
    path(
        "admin/orders/<int:order_id>/update-dates/",
        views.admin_update_order_dates,
        name="admin_update_order_dates",
    ),
    # Transition order status para admin
    path(
        "admin/<int:order_id>/transition/<str:to_status>/",
        views.admin_transition_order,
        name="transition_admin",
    ),
    # ================================================ Medidas - Lifecycle ============================
    path(
        "admin/orders/<int:order_id>/close-measurements/",
        views.close_measurements,
        name="close_measurements",
    ),
    path(
        "admin/orders/<int:order_id>/reopen-measurements/",
        views.reopen_measurements,
        name="reopen_measurements",
    ),
    path(
        "admin/orders/<int:order_id>/lock-measurements/",
        views.lock_measurements,
        name="lock_measurements",
    ),
]

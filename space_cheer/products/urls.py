from django.urls import path
from products import views

app_name = "products"

urlpatterns = [
    path("", views.product_list, name="list_products"),
    # seleccionar plantilla
    path("create/", views.product_create_select_type, name="select_template"),
    # crear producto usando plantilla
    path("create/product/", views.product_create, name="create_product"),
    path("<int:product_id>/edit/", views.product_update, name="update_product"),
    path("<int:product_id>/delete/", views.product_delete, name="delete_product"),
    path(
        "<int:product_id>/configure/",
        views.product_configure,
        name="product_configure",
    ),
    # TALLAS
    path(
        "<int:product_id>/sizes/",
        views.product_sizes,
        name="product_sizes",
    ),
    path(
        "<int:product_id>/sizes/add/",
        views.product_size_add,
        name="product_size_add",
    ),
    # MEDIDAS
    path(
        "<int:product_id>/measurements/",
        views.product_measurements,
        name="product_measurements",
    ),
    path(
        "<int:product_id>/measurements/add/",
        views.product_measurement_add,
        name="product_measurement_add",
    ),
]

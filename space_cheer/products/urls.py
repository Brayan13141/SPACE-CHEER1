from django.urls import path
from products import views

app_name = "products"

urlpatterns = [
    # Lista
    path("", views.product_list, name="list_products"),
    # Crear — paso 1: elegir plantilla
    path("create/", views.product_create_select_type, name="select_template"),
    # Crear — paso 2: formulario
    path("create/new/", views.product_create, name="create_product"),
    # Detalle: editar, toggle activo, tallas, medidas — todo aquí
    path("<int:product_id>/", views.product_detail, name="product_detail"),
]

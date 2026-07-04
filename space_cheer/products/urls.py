from django.urls import path
from products import views

app_name = "products"

urlpatterns = [
    # Catálogo público
    path("catalog/", views.catalog_view, name="catalog"),
    # Lista
    path("", views.product_list, name="list_products"),
    # Crear — paso 1: elegir plantilla
    path("create/", views.product_create_select_type, name="select_template"),
    # Crear — paso 2: formulario
    path("create/new/", views.product_create, name="create_product"),
    # Detalle: editar, toggle activo, tallas, medidas — todo aquí
    path("<int:product_id>/", views.product_detail, name="product_detail"),
    # ─── DEV/TEST ONLY: Previsualización 3D scaffold (no integrar en prod) ───
    path("dev/preview3d-test/", views.preview3d_test_view, name="preview3d_test"),
]

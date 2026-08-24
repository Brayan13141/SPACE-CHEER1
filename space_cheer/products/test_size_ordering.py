"""Las tallas se listan en orden de escala, no alfabetico.

`order_by("size")` devuelve L, M, S, XL, XS, XXL. La hoja de produccion y la
rejilla de tallas ya usan la escala (`orders/services/sizes/ordering.py`); estas
tres pantallas se quedaron con el orden viejo, asi que el mismo producto sale
en un orden en una pantalla y en otro en la de al lado.
"""

import pytest
from django.contrib.admin.sites import AdminSite
from django.test import Client, RequestFactory
from django.urls import reverse

from orders.tests.factories import (
    ProductFactory,
    RoleFactory,
    TeamOrderFactory,
    UserFactory,
)
from products.admin import ProductAdmin
from products.models import Product, ProductSizeVariant

pytestmark = pytest.mark.django_db

# Alfabeticamente saldrian M, XS, XXL: cualquiera de las tres sirve para
# distinguir un orden del otro.
DESORDENADAS = ["XXL", "M", "XS"]
EN_ESCALA = ["XS", "M", "XXL"]


def _producto_con_tallas(tallas=DESORDENADAS, **kwargs):
    product = ProductFactory(size_strategy="STANDARD", is_active=True, **kwargs)
    # El factory siembra CH/M/G/XG por su cuenta para cumplir la regla de
    # dominio "STANDARD requiere variantes"; aca hace falta un juego concreto.
    product.size_variants.all().delete()
    for size in tallas:
        ProductSizeVariant.objects.create(product=product, size=size)
    return product


def _admin_client():
    role = RoleFactory(name="ADMIN")
    user = UserFactory(profile_completed=True, roles=[role])
    client = Client()
    client.force_login(user)
    return client


class TestElDetalleDelProducto:
    """`products/views.py` — la pantalla donde se editan las tallas."""

    def test_lista_las_tallas_en_orden_de_escala(self):
        product = _producto_con_tallas()
        client = _admin_client()

        resp = client.get(reverse("products:product_detail", args=[product.id]))

        assert [v.size for v in resp.context["size_variants"]] == EN_ESCALA


class TestAgregarProductoAlPedido:
    """`orders/views/product_views.py` — el selector de productos del pedido.

    Aca el orden viaja dentro de un `Prefetch`, asi que no alcanza con
    reordenar una lista despues.
    """

    def test_cada_producto_trae_sus_tallas_en_orden_de_escala(self):
        order = TeamOrderFactory()
        product = _producto_con_tallas(is_configured=True)
        client = Client()
        client.force_login(order.created_by)

        resp = client.get(
            reverse("orders:add_item_product_order", args=[order.id])
        )

        listado = {p.id: p for p in resp.context["products"]}
        assert product.id in listado, "el producto no llego al selector"
        tallas = [v.size for v in listado[product.id].size_variants.all()]
        assert tallas == EN_ESCALA


class TestElAdminDeProductos:
    """`products/admin.py` — mismo `Prefetch`, mismo orden viejo."""

    def test_el_queryset_prefetchea_las_tallas_en_orden_de_escala(self):
        product = _producto_con_tallas()
        request = RequestFactory().get("/admin/products/product/")
        request.user = UserFactory(is_superuser=True, is_staff=True)

        qs = ProductAdmin(Product, AdminSite()).get_queryset(request)

        fila = next(p for p in qs if p.id == product.id)
        assert [v.size for v in fila.size_variants.all()] == EN_ESCALA


class TestUnaTallaFueraDeLaEscala:
    """Calzado numerico, por ejemplo: no se le inventa una posicion, va al
    final. Si se colara al principio, la fila de corte empezaria por algo que
    el taller no espera ahi."""

    def test_va_al_final_y_no_rompe_el_orden_de_las_demas(self):
        # La BD real tiene calzado numerico (23-30) junto a XS..XXL.
        product = _producto_con_tallas(tallas=["26", "XXL", "M"])
        client = _admin_client()

        resp = client.get(reverse("products:product_detail", args=[product.id]))

        assert [v.size for v in resp.context["size_variants"]] == [
            "M",
            "XXL",
            "26",
        ]

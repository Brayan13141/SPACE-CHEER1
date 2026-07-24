"""Regresión: las vistas de gestión de productos deben usar el sistema de roles
de la app (role_required), no el sistema de permisos nativo de Django
(permission_required), que nunca se asigna a ningún usuario y bloqueaba con
403 a cualquier ADMIN que no fuera también superuser de Django."""
import pytest
from django.test import Client
from django.urls import reverse

from orders.tests.factories import UserFactory, RoleFactory, ProductFactory

pytestmark = pytest.mark.django_db


def _admin_client():
    role = RoleFactory(name="ADMIN")
    user = UserFactory(profile_completed=True, roles=[role])
    client = Client()
    client.force_login(user)
    return client


class TestProductDetailAccess:
    def test_admin_role_sin_superuser_puede_ver_detalle(self):
        client = _admin_client()
        product = ProductFactory(is_active=True)
        resp = client.get(reverse("products:product_detail", args=[product.id]))
        assert resp.status_code == 200

    def test_admin_role_sin_superuser_puede_togglear_activo(self):
        client = _admin_client()
        product = ProductFactory(is_active=True)
        resp = client.post(
            reverse("products:product_detail", args=[product.id]),
            {"action": "toggle_active"},
        )
        product.refresh_from_db()
        assert resp.status_code == 302
        assert product.is_active is False

    def test_admin_role_sin_superuser_puede_crear_producto(self):
        client = _admin_client()
        resp = client.get(reverse("products:select_template"))
        assert resp.status_code == 200

    def test_usuario_sin_rol_admin_no_puede_ver_detalle(self):
        user = UserFactory(profile_completed=True)
        client = Client()
        client.force_login(user)
        product = ProductFactory(is_active=True)
        resp = client.get(reverse("products:product_detail", args=[product.id]))
        assert resp.status_code == 302  # role_required redirige, no 403

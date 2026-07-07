"""Tests del scope INTERNAL (productos de taller, fuera de catálogo)."""
import pytest
from django.core.exceptions import ValidationError

from orders.tests.factories import ProductFactory, SeasonFactory, TeamFactory

pytestmark = pytest.mark.django_db


def _internal(**kw):
    kw.setdefault("scope", "INTERNAL")
    kw.setdefault("usage_type", "GLOBAL")
    kw.setdefault("size_strategy", "NONE")
    return ProductFactory(**kw)


class TestInternalScope:
    def test_internal_valido_sin_owner_team(self):
        p = _internal()
        assert p.scope == "INTERNAL"
        assert p.owner_team is None

    def test_internal_permite_measurements_con_usage_global(self):
        # Excepción a la regla "GLOBAL no puede usar medidas"
        p = _internal(size_strategy="MEASUREMENTS")
        assert p.size_strategy == "MEASUREMENTS"

    def test_global_catalog_sigue_sin_poder_usar_measurements(self):
        with pytest.raises(ValidationError):
            ProductFactory(scope="CATALOG", usage_type="GLOBAL", size_strategy="MEASUREMENTS")

    def test_internal_no_permite_owner_team(self):
        with pytest.raises(ValidationError):
            _internal(owner_team=TeamFactory())

    def test_internal_fuera_del_catalogo(self):
        from orders.services.cart import CartService
        from orders.tests.factories import UserFactory
        p = _internal()
        qs = CartService.get_catalog_queryset(UserFactory())
        assert p not in qs

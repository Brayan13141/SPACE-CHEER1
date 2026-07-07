# accounts/test_seed_products.py
"""
Tests del comando seed_products.

Verifica que las categorías de equipo se creen desde la taxonomía USASF
completa de seed_categories (single source of truth) y no desde una lista
propia desactualizada.
"""

from io import StringIO

import pytest
from django.core.management import call_command

from teams.management.commands.seed_categories import CATEGORIES
from teams.models import TeamCategory

pytestmark = pytest.mark.django_db


def _run_seed_products():
    out = StringIO()
    call_command("seed_products", stdout=out)
    return out.getvalue()


class TestSeedProductsTeamCategories:
    def test_crea_taxonomia_usasf_completa(self):
        _run_seed_products()

        for name, level, _description in CATEGORIES:
            assert TeamCategory.objects.filter(
                name=name, level=level
            ).exists(), f"Falta categoría USASF: {name} (nivel {level})"

        assert TeamCategory.objects.count() == len(CATEGORIES)

    def test_no_crea_categorias_legacy_hardcodeadas(self):
        _run_seed_products()

        assert not TeamCategory.objects.filter(
            name__in=[
                "Juvenil Nivel 1",
                "Juvenil Nivel 2",
                "Juvenil Nivel 3",
                "Senior Nivel 1",
                "Senior Nivel 2",
            ]
        ).exists()

    def test_es_idempotente(self):
        _run_seed_products()
        count_first = TeamCategory.objects.count()

        _run_seed_products()

        assert TeamCategory.objects.count() == count_first

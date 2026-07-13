# production/test_seed_production_templates.py
"""
Tests del comando seed_production_templates.

F4 (hallazgo 6.2): sin ningún ProductionTemplate en la BD, los productos al
vuelo de pedidos OFFLINE nacen sin etapas configuradas y su ProductionJob
queda sin tasks para siempre. Este seed crea un template por defecto,
idempotente, para que el selector de plantilla de la UI offline nunca esté
vacío.
"""

from io import StringIO

import pytest
from django.core.management import call_command

from production.management.commands.seed_production_templates import TEMPLATES
from production.models import ProductionStage, ProductionTemplate, ProductionTemplateStage

pytestmark = pytest.mark.django_db


def _run_seed():
    call_command("seed_production_stages")
    out = StringIO()
    call_command("seed_production_templates", stdout=out)
    return out.getvalue()


class TestSeedProductionTemplates:
    def test_crea_al_menos_un_template(self):
        _run_seed()
        assert ProductionTemplate.objects.exists()

    def test_templates_definidos_se_crean_con_sus_etapas(self):
        _run_seed()

        for data in TEMPLATES:
            template = ProductionTemplate.objects.filter(name=data["name"]).first()
            assert template is not None, f"Falta template: {data['name']}"

            stage_slugs = set(
                ProductionTemplateStage.objects.filter(template=template).values_list(
                    "stage__slug", flat=True
                )
            )
            assert stage_slugs == set(data["stage_slugs"])

    def test_es_idempotente(self):
        _run_seed()
        _run_seed()

        assert ProductionTemplate.objects.count() == len(TEMPLATES)
        for data in TEMPLATES:
            template = ProductionTemplate.objects.get(name=data["name"])
            assert (
                ProductionTemplateStage.objects.filter(template=template).count()
                == len(data["stage_slugs"])
            )

    def test_falla_si_faltan_etapas_prerequisito(self):
        # Sin correr seed_production_stages antes: los slugs no existen.
        with pytest.raises(ProductionStage.DoesNotExist):
            call_command("seed_production_templates")

"""Reportar un error de produccion desde el formulario.

Regresion del P0: la vista llamaba a `ErrorReportService.create()` con
`order_id=`/`stage_id=`/`responsible_id=` y el servicio espera los objetos.
El `except Exception` de la vista se tragaba el `TypeError` y respondia con un
"Ocurrio un error al guardar el reporte" y un `302` normal, asi que en
produccion el formulario se veia bien y no guardaba nada. Por eso los tests de
aca miran la fila en la BD, no el codigo de respuesta.
"""

import pytest
from django.urls import reverse

from orders.tests.factories import RoleFactory, TeamOrderFactory, UserFactory
from production.models import (
    ErrorReport,
    ProductionJob,
    ProductionStage,
)

pytestmark = pytest.mark.django_db


def _operario():
    role = RoleFactory(name="OPERARIO", is_production_type=True)
    return UserFactory(profile_completed=True, roles=[role])


def _stage():
    stage, _ = ProductionStage.objects.get_or_create(
        slug="corte", defaults={"name": "Corte", "display_order": 1}
    )
    return stage


class TestCrearUnReporteDeError:

    def test_guarda_el_reporte_con_su_etapa_y_su_responsable(self, client):
        operario = _operario()
        responsable = _operario()
        stage = _stage()
        client.force_login(operario)

        client.post(
            reverse("production:create_error_report"),
            {
                "description": "La tela llego con un corte en el rollo",
                "error_types": ["MATERIAL"],
                "stage": stage.pk,
                "responsible": responsable.pk,
            },
        )

        report = ErrorReport.objects.get()
        assert report.description == "La tela llego con un corte en el rollo"
        assert report.reported_by == operario
        assert report.stage == stage
        assert report.responsible == responsable

    def test_desde_un_job_hereda_el_job_y_su_pedido(self, client):
        operario = _operario()
        order = TeamOrderFactory()
        job = ProductionJob.objects.create(order=order)
        client.force_login(operario)

        client.post(
            reverse("production:create_error_report_job", args=[job.pk]),
            {"description": "Se marco la prenda al planchar", "error_types": ["PROCESO"]},
        )

        report = ErrorReport.objects.get()
        assert report.job == job
        assert report.order == order

    def test_sin_etapa_ni_responsable_igual_guarda(self, client):
        """Los dos campos son opcionales en el formulario."""
        operario = _operario()
        client.force_login(operario)

        client.post(
            reverse("production:create_error_report"),
            {"description": "Falto hilo del color correcto", "error_types": []},
        )

        assert ErrorReport.objects.count() == 1
        report = ErrorReport.objects.get()
        assert report.stage is None
        assert report.responsible is None

    def test_sin_descripcion_no_guarda_nada(self, client):
        operario = _operario()
        client.force_login(operario)

        client.post(
            reverse("production:create_error_report"),
            {"description": "   ", "error_types": ["MATERIAL"]},
        )

        assert not ErrorReport.objects.exists()

from datetime import date, timedelta

import pytest
from django.core.exceptions import PermissionDenied

from accounts.models import AthleteProfile, PiiAccessLog
from orders.services.sizes.SizeGridService import SizeGridService
from orders.tests.factories import (
    AthleteFactory,
    AthleteStandardSizeFactory,
    CoachFactory,
    TeamOrderFactory,
    TeamProductWithSizesFactory,
    UserTeamMembershipFactory,
)


def setup_team_roster(sizes=None, athlete_count=3):
    """Helper A NIVEL DE MODULO, no un metodo de una clase de test.

    Las otras clases de test de este archivo lo llaman directamente; instanciar
    una clase de test desde otra (TestX()._setup()) funciona por accidente en
    pytest y es justo lo que un reviewer marca.
    """
    order = TeamOrderFactory()
    product = TeamProductWithSizesFactory(sizes=sizes)
    athletes = [AthleteFactory() for _ in range(athlete_count)]
    for athlete in athletes:
        UserTeamMembershipFactory(user=athlete, team=order.owner_team)
    return order, product, athletes


def make_minor_with_guardian(athlete, guardian):
    """is_minor es False cuando birth_date es None, asi que un 'menor' sin
    fecha de nacimiento hace fallar todo el scoping del tutor en silencio."""
    athlete.birth_date = date.today() - timedelta(days=365 * 12)
    athlete.save()
    AthleteProfile.objects.update_or_create(
        user=athlete, defaults={"guardian": guardian}
    )


@pytest.mark.django_db
class TestSizeAccessTypes:

    def test_los_tipos_de_acceso_a_talla_existen(self):
        codes = {code for code, _ in PiiAccessLog.ACCESS_TYPES}

        assert "VIEW_SIZE" in codes
        assert "EDIT_SIZE" in codes


@pytest.mark.django_db
class TestSizeGridBuild:

    def _setup(self):
        return setup_team_roster()

    def test_una_fila_por_alumno_del_equipo(self):
        order, product, athletes = self._setup()

        grid = SizeGridService.build(order, product, order.created_by)

        assert len(grid.rows) == 3
        assert grid.total_count == 3
        assert grid.assigned_count == 0

    def test_prellena_con_la_talla_guardada_del_alumno(self):
        order, product, (a1, a2, a3) = self._setup()
        AthleteStandardSizeFactory(user=a1, size="L")

        grid = SizeGridService.build(order, product, order.created_by)
        row = next(r for r in grid.rows if r.athlete_id == a1.id)

        assert row.size == "L"

    def test_no_prellena_una_talla_que_el_producto_no_ofrece(self):
        order, product, (a1, a2, a3) = self._setup()
        product.size_variants.filter(size="XXL").delete()
        AthleteStandardSizeFactory(user=a1, size="XXL")

        grid = SizeGridService.build(order, product, order.created_by)
        row = next(r for r in grid.rows if r.athlete_id == a1.id)

        assert row.size == ""

    def test_el_tutor_solo_ve_y_escribe_la_fila_de_su_hijo(self):
        order, product, (a1, a2, a3) = self._setup()
        guardian = CoachFactory()
        make_minor_with_guardian(a1, guardian)

        grid = SizeGridService.build(order, product, guardian)

        assert [r.athlete_id for r in grid.rows] == [a1.id]
        assert grid.rows[0].editable is True

    def test_un_extrano_no_ve_nada(self):
        order, product, athletes = self._setup()
        intruso = CoachFactory()

        with pytest.raises(PermissionDenied):
            SizeGridService.build(order, product, intruso)

    def test_orden_no_editable_deja_el_grid_bloqueado(self):
        order, product, athletes = self._setup()
        order.measurements_locked = True
        order.save()

        grid = SizeGridService.build(order, product, order.created_by)

        assert grid.can_edit is False
        assert grid.is_locked is True

    def test_una_orden_que_no_es_de_equipo_no_arma_grid(self):
        order, product, athletes = self._setup()
        order.order_type = "PERSONAL"

        with pytest.raises(PermissionDenied):
            SizeGridService.build(order, product, order.created_by)

    def test_assignments_from_post_ignora_las_filas_ajenas(self):
        """SEGURIDAD: el tutor postea la celda de otro menor a mano y no pasa."""
        order, product, (a1, a2, a3) = self._setup()
        guardian = CoachFactory()
        make_minor_with_guardian(a1, guardian)
        grid = SizeGridService.build(order, product, guardian)

        assignments = SizeGridService.assignments_from_post(
            grid, {f"size_{a1.id}": "M", f"size_{a2.id}": "XL"}
        )

        assert assignments == {a1.id: "M"}

from datetime import date, timedelta

import pytest
from django.core.exceptions import PermissionDenied
from django.urls import reverse

from accounts.models import AthleteProfile, PiiAccessLog
from measures.models import AthleteStandardSize
from orders.services.sizes.SizeGridService import SizeGridService
from orders.tests.factories import (
    AthleteFactory,
    AthleteStandardSizeFactory,
    CoachFactory,
    TeamOrderFactory,
    TeamProductWithSizesFactory,
    UserFactory,
    RoleFactory,
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

    def test_el_coach_del_equipo_ve_todo_pero_no_escribe_si_no_creo_el_pedido(self):
        """La rama es alcanzable cuando un ADMIN crea el pedido a nombre del
        coach: el coach del equipo ve el roster completo (es Team.coach, asi que
        visible_for_user lo incluye) pero no es created_by ni ADMIN, y por eso
        can_write queda en False. Sin este test un refactor vuelve ese elif un
        `True` plano y nada chilla."""
        order, product, athletes = self._setup()
        order.created_by = UserFactory()
        order.save()
        coach_del_equipo = order.owner_team.coach

        grid = SizeGridService.build(order, product, coach_del_equipo)

        assert len(grid.rows) == 3          # ve todas las filas
        assert grid.can_edit is False       # y no puede escribir ninguna
        assert grid.is_locked is False      # y NO es porque la orden este bloqueada

    def test_una_orden_que_no_es_de_equipo_no_arma_grid(self):
        order, product, athletes = self._setup()
        order.order_type = "PERSONAL"

        with pytest.raises(PermissionDenied):
            SizeGridService.build(order, product, order.created_by)

    def test_un_producto_fuera_del_catalogo_de_la_orden_no_arma_grid(self):
        """SEGURIDAD: si el producto no se puede pedir en esta orden, la
        pantalla no se ofrece siquiera. Espeja la guarda de reconcile()."""
        order, product, athletes = self._setup()
        product.season.is_active = False
        product.season.save()

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


def setup_view_case(client):
    """Helper A NIVEL DE MODULO — lo usan TestSizeGridView, la clase de
    auditoria y la del detalle del item. No instanciar una clase de test
    desde otra."""
    order, product, athletes = setup_team_roster(athlete_count=2)
    client.force_login(order.created_by)
    url = reverse(
        "orders:order_product_sizes_grid",
        args=[order.id, product.id],
    )
    return order, product, athletes, url


@pytest.mark.django_db
class TestSizeGridView:

    def _setup(self, client):
        return setup_view_case(client)

    def test_get_renderiza_el_roster(self, client):
        order, product, athletes, url = self._setup(client)

        response = client.get(url)

        assert response.status_code == 200
        assert len(response.context["grid"].rows) == 2

    def test_post_guarda_y_redirige_al_propio_grid(self, client):
        order, product, (a1, a2), url = self._setup(client)

        response = client.post(url, {f"size_{a1.id}": "M", f"size_{a2.id}": "L"})

        assert response.status_code == 302
        assert response.url == url
        assert order.items.count() == 2

    def test_post_con_una_talla_invalida_rerenderiza_sin_perder_lo_tecleado(self, client):
        order, product, (a1, a2), url = self._setup(client)
        product.size_variants.filter(size="XXL").delete()

        response = client.post(url, {f"size_{a1.id}": "XXL", f"size_{a2.id}": "L"})

        assert response.status_code == 200
        grid = response.context["grid"]
        row = next(r for r in grid.rows if r.athlete_id == a1.id)
        assert row.error
        # La captura del otro alumno SI se guardo: fallo por fila, no por POST.
        assert order.items.filter(size_variant__size="L").exists()

    def test_post_sobre_orden_bloqueada_avisa_en_vez_de_reventar(self, client):
        order, product, (a1, a2), url = setup_view_case(client)
        order.measurements_locked = True
        order.save()

        response = client.post(url, {f"size_{a1.id}": "M"})

        assert response.status_code == 200      # no 500, no 403 pelado
        assert not order.items.exists()         # nada se guardo
        # El intento igual muestra el roster completo, asi que se audita: sin
        # esta asercion, quien "simplifique" el return de esa rama y borre la
        # linea de auditoria pasa igual toda la suite.
        assert PiiAccessLog.objects.filter(access_type="VIEW_SIZE").count() == 2


    def test_post_sin_permiso_de_escritura_no_dice_que_la_orden_esta_cerrada(self, client):
        """Dos causas distintas piden dos mensajes: "la orden esta cerrada" y
        "ves el roster pero no lo capturas tu" no son lo mismo, y el propio
        docstring de SizeGrid avisa que confundirlas es mentirle al usuario."""
        order, product, athletes, url = setup_view_case(client)
        order.created_by = UserFactory()
        order.save()
        client.force_login(order.owner_team.coach)

        response = client.post(url, {f"size_{athletes[0].id}": "M"})

        assert response.status_code == 200
        avisos = [str(m) for m in response.context["messages"]]
        assert avisos == [SizeGridService.NO_WRITE_MESSAGE]
        assert not order.items.exists()


@pytest.mark.django_db
class TestSizeGridAuditoria:

    def test_ver_el_grid_deja_un_registro_por_alumno(self, client):
        order, product, athletes, url = setup_view_case(client)

        client.get(url)

        logs = PiiAccessLog.objects.filter(access_type="VIEW_SIZE")
        assert logs.count() == 2

    def test_recargar_no_duplica_la_bitacora(self, client):
        order, product, athletes, url = setup_view_case(client)

        client.get(url)
        client.get(url)

        assert PiiAccessLog.objects.filter(access_type="VIEW_SIZE").count() == 2

    def test_guardar_deja_edit_size_por_alumno_tocado(self, client):
        order, product, (a1, a2), url = setup_view_case(client)

        client.post(url, {f"size_{a1.id}": "M", f"size_{a2.id}": ""})

        logs = PiiAccessLog.objects.filter(access_type="EDIT_SIZE")
        assert list(logs.values_list("target_user_id", flat=True)) == [a1.id]

    def test_un_post_rechazado_tambien_deja_rastro(self, client):
        order, product, (a1, a2), url = setup_view_case(client)
        product.size_variants.filter(size="XXL").delete()

        client.post(url, {f"size_{a1.id}": "XXL"})

        assert PiiAccessLog.objects.filter(access_type="VIEW_SIZE").count() == 2

from datetime import date, timedelta

import pytest
from django.core.exceptions import PermissionDenied
from django.urls import reverse

from accounts.models import AthleteProfile, PiiAccessLog
from measures.models import AthleteStandardSize
from orders.services.servicesItems.size_assignment_service import (
    OrderItemSizeAssignmentService,
)
from orders.services.sizes.SizeGridService import SizeGridService
from orders.services.sizes.SizeSummaryService import SizeSummaryService
from orders.tests.factories import (
    AthleteFactory,
    AthleteStandardSizeFactory,
    CoachFactory,
    TeamOrderFactory,
    TeamProductWithSizesFactory,
    UserFactory,
    OrderItemFactory,
    ProductFactory,
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


@pytest.mark.django_db
class TestTallaEnPerfilDelAtleta:
    """La talla es un dato del ALUMNO (Decision 1), asi que tambien se captura
    donde viven sus medidas, no solo desde el roster de un pedido."""

    def _setup(self, client):
        order = TeamOrderFactory()
        coach = order.owner_team.coach
        athlete = AthleteFactory()
        UserTeamMembershipFactory(user=athlete, team=order.owner_team)
        client.force_login(coach)
        url = reverse("coach:edit_athlete_measures", args=[athlete.id])
        return athlete, url

    def test_el_coach_guarda_la_talla_del_alumno(self, client):
        athlete, url = self._setup(client)

        response = client.post(url, {"standard_size": "L"})

        assert response.status_code == 302
        assert AthleteStandardSize.objects.get(user=athlete).size == "L"
        assert PiiAccessLog.objects.filter(
            access_type="EDIT_SIZE", target_user=athlete
        ).count() == 1

    def test_vaciar_el_selector_borra_la_talla_y_deja_rastro(self, client):
        athlete, url = self._setup(client)
        AthleteStandardSizeFactory(user=athlete, size="M")

        client.post(url, {"standard_size": ""})

        assert not AthleteStandardSize.objects.filter(user=athlete).exists()
        assert PiiAccessLog.objects.filter(
            access_type="EDIT_SIZE", target_user=athlete
        ).count() == 1

    def test_guardar_la_misma_talla_no_ensucia_la_bitacora(self, client):
        athlete, url = self._setup(client)
        AthleteStandardSizeFactory(user=athlete, size="M")

        client.post(url, {"standard_size": "M"})

        assert not PiiAccessLog.objects.filter(access_type="EDIT_SIZE").exists()


@pytest.mark.django_db
class TestDetalleDelItemConTallas:
    """El item por talla se ve desde el detalle: sin esto, la talla existe en la
    base pero nadie ve QUIEN la lleva sin volver al roster."""

    def test_el_detalle_lista_los_alumnos_de_esa_talla(self, client):
        order, product, (a1, a2), url = setup_view_case(client)
        client.post(url, {f"size_{a1.id}": "M", f"size_{a2.id}": "M"})
        item = order.items.get(size_variant__size="M")

        response = client.get(reverse("orders:order_item_detail", args=[item.id]))

        assert response.status_code == 200
        cuerpo = response.content.decode()
        assert a1.get_full_name() in cuerpo
        assert a2.get_full_name() in cuerpo

    def test_hay_enlace_al_grid_de_tallas(self, client):
        order, product, (a1, a2), url = setup_view_case(client)
        client.post(url, {f"size_{a1.id}": "M"})
        item = order.items.get(size_variant__size="M")

        response = client.get(reverse("orders:order_item_detail", args=[item.id]))

        assert url in response.content.decode()


@pytest.mark.django_db
class TestPanelAdminConTallas:

    def test_el_admin_ve_los_alumnos_y_llega_al_grid_de_tallas(self, client):
        order, product, (a1, a2), url = setup_view_case(client)
        client.post(url, {f"size_{a1.id}": "M", f"size_{a2.id}": "M"})

        admin = UserFactory(profile_completed=True)
        admin.roles.add(RoleFactory(name="ADMIN"))
        client.force_login(admin)
        response = client.get(
            reverse("orders:admin_order_detail", kwargs={"order_id": order.id})
        )

        cuerpo = response.content.decode()
        assert a1.get_full_name() in cuerpo
        assert url in cuerpo          # puede saltar al roster desde el panel

    def test_el_item_por_talla_no_muestra_badges_de_medidas(self, client):
        """El badge "Medidas pendientes" es de productos MEASUREMENTS; en un
        item por talla no aplica y solo confunde: ese producto no pide medidas."""
        order, product, (a1, a2), url = setup_view_case(client)
        client.post(url, {f"size_{a1.id}": "M"})

        admin = UserFactory(profile_completed=True)
        admin.roles.add(RoleFactory(name="ADMIN"))
        client.force_login(admin)
        response = client.get(
            reverse("orders:admin_order_detail", kwargs={"order_id": order.id})
        )

        assert "Medidas pendientes" not in response.content.decode()


@pytest.mark.django_db
class TestResumenDeTallas:
    """Un pedido de 12 playeras son 3 OrderItem (uno por talla). Sin agrupar,
    la pantalla repite el producto y el boton de captura una vez por talla."""

    def test_agrupa_los_items_por_producto_con_su_desglose(self):
        order, product, athletes = setup_team_roster(athlete_count=4)
        OrderItemSizeAssignmentService.reconcile(
            order, product,
            {athletes[0].id: "M", athletes[1].id: "M", athletes[2].id: "L"},
            viewer=order.created_by,
        )

        resumen = SizeSummaryService.for_order(order)

        assert len(resumen) == 1
        grupo = resumen[0]
        assert grupo.product == product
        assert grupo.rows == [("M", 2), ("L", 1)]
        assert grupo.assigned == 3
        assert grupo.total == 4
        assert grupo.missing == 1

    def test_ignora_los_productos_que_no_usan_talla_por_alumno(self):
        order, product, athletes = setup_team_roster()
        OrderItemSizeAssignmentService.reconcile(
            order, product, {athletes[0].id: "M"}, viewer=order.created_by
        )
        OrderItemFactory(order=order, product=ProductFactory())

        resumen = SizeSummaryService.for_order(order)

        assert [grupo.product for grupo in resumen] == [product]

    def test_un_pedido_sin_items_por_talla_no_trae_resumen(self):
        order = TeamOrderFactory()
        OrderItemFactory(order=order, product=ProductFactory())

        assert SizeSummaryService.for_order(order) == []


@pytest.mark.django_db
class TestUnSoloBotonDeTallas:
    """Bryan: "no entiendo por que cada item tiene el boton de capturar las
    tallas si con uno solo se muestran las tallas de todos los alumnos"."""

    def _con_dos_tallas(self, client):
        order, product, (a1, a2), url = setup_view_case(client)
        client.post(url, {f"size_{a1.id}": "M", f"size_{a2.id}": "L"})
        assert order.items.count() == 2
        return order, product, url

    def test_el_detalle_del_pedido_agrupa_y_deja_un_solo_boton(self, client):
        order, product, url = self._con_dos_tallas(client)

        response = client.get(reverse("orders:detail_order", args=[order.id]))

        cuerpo = response.content.decode()
        assert cuerpo.count(url) == 1
        grupos = response.context["size_groups"]
        assert len(grupos) == 1
        assert grupos[0].assigned == 2

    def test_el_panel_admin_tambien_deja_un_solo_boton(self, client):
        order, product, url = self._con_dos_tallas(client)
        admin = UserFactory(profile_completed=True)
        admin.roles.add(RoleFactory(name="ADMIN"))
        client.force_login(admin)

        response = client.get(
            reverse("orders:admin_order_detail", kwargs={"order_id": order.id})
        )

        assert response.content.decode().count(url) == 1

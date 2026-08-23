"""La hoja de tallas que producción imprime para el taller."""

import pytest
from django.urls import reverse

from accounts.models import PiiAccessLog, Role
from orders.services.servicesItems.size_assignment_service import (
    OrderItemSizeAssignmentService,
)
from orders.tests.factories import (
    AthleteFactory,
    OrderItemFactory,
    ProductFactory,
    TeamOrderFactory,
    TeamProductWithSizesFactory,
    UserFactory,
    UserTeamMembershipFactory,
)
from production.models import ProductionJob, ProductionStage, ProductionTask


def make_operario():
    role, _ = Role.objects.get_or_create(
        name="OPERARIO", defaults={"is_production_type": True}
    )
    user = UserFactory(profile_completed=True)
    user.roles.add(role)
    return user


def make_admin():
    role, _ = Role.objects.get_or_create(name="ADMIN")
    user = UserFactory(profile_completed=True)
    user.roles.add(role)
    return user


def dale_trabajo(order, operario):
    """Le da al operario una tarea en ese pedido, que es lo que lo habilita."""
    job, _ = ProductionJob.objects.get_or_create(order=order)
    stage, _ = ProductionStage.objects.get_or_create(
        slug="corte", defaults={"name": "Corte", "display_order": 1}
    )
    ProductionTask.objects.create(
        job=job,
        order_item=order.items.first(),
        stage=stage,
        assigned_to=operario,
    )
    return job


def con_tallas(athlete_count=4, asignadas=None):
    order = TeamOrderFactory()
    product = TeamProductWithSizesFactory()
    athletes = [AthleteFactory() for _ in range(athlete_count)]
    for athlete in athletes:
        UserTeamMembershipFactory(user=athlete, team=order.owner_team)
    if asignadas is None:
        asignadas = {athletes[0].id: "M", athletes[1].id: "M", athletes[2].id: "L"}
    OrderItemSizeAssignmentService.reconcile(
        order, product, asignadas, viewer=order.created_by
    )
    url = reverse("production:order_sizes_print", args=[order.id])
    return order, product, athletes, url


@pytest.mark.django_db
class TestHojaDeTallasDeProduccion:

    def test_imprime_el_corte_con_una_columna_por_talla(self, client):
        order, product, athletes, url = con_tallas()
        client.force_login(make_admin())

        response = client.get(url)

        assert response.status_code == 200
        grupo = response.context["size_groups"][0]
        assert [(f.size, f.quantity) for f in grupo.rows] == [("M", 2), ("L", 1)]
        assert grupo.quantity == 3

    def test_las_tallas_salen_en_orden_de_escala_y_no_por_cantidad(self, client):
        """En una hoja de corte se busca UNA talla concreta, asi que manda la
        escala. Con el orden viejo (mas alumnos primero) este reparto salia
        M, XS, XXL y habia que barrer toda la fila para encontrar la XS."""
        order = TeamOrderFactory()
        product = TeamProductWithSizesFactory()
        athletes = [AthleteFactory() for _ in range(5)]
        for athlete in athletes:
            UserTeamMembershipFactory(user=athlete, team=order.owner_team)
        OrderItemSizeAssignmentService.reconcile(
            order,
            product,
            {
                athletes[0].id: "XS",
                athletes[1].id: "M",
                athletes[2].id: "M",
                athletes[3].id: "M",
                athletes[4].id: "XXL",
            },
            viewer=order.created_by,
        )
        client.force_login(make_admin())

        response = client.get(
            reverse("production:order_sizes_print", args=[order.id])
        )

        grupo = response.context["size_groups"][0]
        assert [f.size for f in grupo.rows] == ["XS", "M", "XXL"]

    def test_el_reparto_nombra_a_cada_alumno_con_su_talla(self, client):
        order, product, athletes, url = con_tallas()
        client.force_login(make_admin())

        cuerpo = client.get(url).content.decode()

        for athlete in athletes[:3]:
            assert (athlete.get_full_name() or athlete.email) in cuerpo

    def test_marca_a_quien_no_tiene_talla(self, client):
        """El de la cuarta fila no entro en ninguna talla: si la hoja no lo
        nombra, el taller corta 3 y nadie se entera hasta la entrega."""
        order, product, athletes, url = con_tallas()
        client.force_login(make_admin())

        cuerpo = client.get(url).content.decode()

        sin_talla = athletes[3]
        assert (sin_talla.get_full_name() or sin_talla.email) in cuerpo
        assert "SIN TALLA" in cuerpo

    def test_audita_tambien_a_los_que_salen_marcados_sin_talla(self, client):
        """Salen impresos con nombre y apellido: auditar solo a los que tienen
        OrderItemAthlete deja fuera justo a esos."""
        order, product, athletes, url = con_tallas()
        client.force_login(make_admin())

        client.get(url)

        registrados = set(
            PiiAccessLog.objects.filter(access_type="VIEW_SIZE").values_list(
                "target_user_id", flat=True
            )
        )
        assert {a.id for a in athletes} <= registrados

    def test_el_corte_imprime_la_cantidad_del_pedido_no_el_numero_de_alumnos(
        self, client
    ):
        """Un item agregado a mano lleva cantidad y ningun atleta: imprimir el
        conteo de alumnos daba "0 piezas" para un pedido que cobra 5."""
        order, product, athletes, url = con_tallas()
        item = order.items.get(size_variant__size="L")
        item.quantity = 5
        item.save()
        client.force_login(make_admin())

        response = client.get(url)

        fila = next(
            f for f in response.context["size_groups"][0].rows if f.size == "L"
        )
        assert fila.quantity == 5
        assert fila.assigned == 1
        assert fila.sin_repartir == 4
        assert "5" in response.content.decode()


@pytest.mark.django_db
class TestQuienPuedeImprimirla:
    """La hoja se lleva nombre y talla de menores al taller."""

    def test_el_operario_con_trabajo_en_el_pedido_entra(self, client):
        order, product, athletes, url = con_tallas()
        operario = make_operario()
        dale_trabajo(order, operario)
        client.force_login(operario)

        assert client.get(url).status_code == 200

    def test_el_operario_sin_trabajo_en_el_pedido_no_entra(self, client):
        """Sin esta guarda cualquier operario recorre /pedido/<n>/ y saca el
        roster completo de todos los equipos."""
        order, product, athletes, url = con_tallas()
        client.force_login(make_operario())

        assert client.get(url).status_code == 404

    def test_el_admin_entra_a_cualquier_pedido(self, client):
        order, product, athletes, url = con_tallas()
        client.force_login(make_admin())

        assert client.get(url).status_code == 200

    def test_un_extrano_no_entra(self, client):
        order, product, athletes, url = con_tallas()
        client.force_login(UserFactory(profile_completed=True))

        response = client.get(url)

        assert response.status_code in (302, 403, 404)

    def test_un_pedido_sin_productos_por_talla_no_tiene_hoja(self, client):
        """404, no 403: no es un problema de permisos, y el boton del panel de
        produccion es incondicional, asi que se llega aca sin culpa."""
        order = TeamOrderFactory()
        OrderItemFactory(order=order, product=ProductFactory())
        client.force_login(make_admin())

        response = client.get(
            reverse("production:order_sizes_print", args=[order.id])
        )

        assert response.status_code == 404


@pytest.mark.django_db
class TestLaHojaSobreviveAlCSP:
    """script-src y style-src son 'self' + nonce, sin unsafe-inline: sin nonce
    el navegador descarta el bloque entero y la hoja imprime con navbar, en
    tema oscuro y sin saltos de pagina. En el HTML se ve igual, asi que curl no
    lo detecta y hace falta asertarlo."""

    def test_el_style_de_impresion_lleva_nonce(self, client):
        order, product, athletes, url = con_tallas()
        client.force_login(make_admin())

        cuerpo = client.get(url).content.decode()

        assert "<style nonce=" in cuerpo
        assert "@media print" in cuerpo

    def test_el_boton_de_imprimir_no_usa_un_handler_inline(self, client):
        order, product, athletes, url = con_tallas()
        client.force_login(make_admin())

        cuerpo = client.get(url).content.decode()

        assert "onclick=" not in cuerpo
        assert "<script nonce=" in cuerpo

    def test_la_hoja_no_muestra_comentarios_de_plantilla_en_crudo(self, client):
        order, product, athletes, url = con_tallas()
        client.force_login(make_admin())

        cuerpo = client.get(url).content.decode()

        assert "{#" not in cuerpo
        assert "{% comment" not in cuerpo

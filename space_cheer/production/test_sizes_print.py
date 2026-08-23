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


def make_operario():
    role, _ = Role.objects.get_or_create(
        name="OPERARIO", defaults={"is_production_type": True}
    )
    user = UserFactory(profile_completed=True)
    user.roles.add(role)
    return user


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
        client.force_login(make_operario())

        response = client.get(url)

        assert response.status_code == 200
        grupo = response.context["size_groups"][0]
        assert [(f.size, f.assigned) for f in grupo.rows] == [("M", 2), ("L", 1)]
        assert grupo.assigned == 3

    def test_el_reparto_nombra_a_cada_alumno_con_su_talla(self, client):
        order, product, athletes, url = con_tallas()
        client.force_login(make_operario())

        cuerpo = client.get(url).content.decode()

        for athlete in athletes[:3]:
            assert (athlete.get_full_name() or athlete.email) in cuerpo

    def test_marca_a_quien_no_tiene_talla(self, client):
        """El de la cuarta fila no entro en ninguna talla: si la hoja no lo
        nombra, el taller corta 3 y nadie se entera hasta la entrega."""
        order, product, athletes, url = con_tallas()
        client.force_login(make_operario())

        cuerpo = client.get(url).content.decode()

        sin_talla = athletes[3]
        assert (sin_talla.get_full_name() or sin_talla.email) in cuerpo
        assert "SIN TALLA" in cuerpo

    def test_registra_view_size_de_los_alumnos_impresos(self, client):
        order, product, athletes, url = con_tallas()
        client.force_login(make_operario())

        client.get(url)

        registrados = set(
            PiiAccessLog.objects.filter(access_type="VIEW_SIZE").values_list(
                "target_user_id", flat=True
            )
        )
        assert {a.id for a in athletes[:3]} <= registrados

    def test_un_extrano_no_entra(self, client):
        order, product, athletes, url = con_tallas()
        client.force_login(UserFactory(profile_completed=True))

        response = client.get(url)

        assert response.status_code in (302, 403)

    def test_un_pedido_sin_productos_por_talla_no_tiene_hoja(self, client):
        order = TeamOrderFactory()
        OrderItemFactory(order=order, product=ProductFactory())
        client.force_login(make_operario())

        response = client.get(
            reverse("production:order_sizes_print", args=[order.id])
        )

        assert response.status_code == 403

    def test_la_hoja_no_muestra_comentarios_de_plantilla_en_crudo(self, client):
        order, product, athletes, url = con_tallas()
        client.force_login(make_operario())

        cuerpo = client.get(url).content.decode()

        assert "{#" not in cuerpo
        assert "{% comment" not in cuerpo

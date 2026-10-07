"""STAFF abre el detalle de cualquier pedido, en solo lectura.

Antes `/orders/<id>/` no admitía el rol y `visible_for_user` tampoco le daba los
pedidos ajenos ni los offline: staff los trabajaba por dentro sin poder verlos.
La lectura se abre SOLO en esta vista; `visible_for_user` sigue decidiendo qué
se puede editar, así que abrirlo ahí le habría dado escritura en todo.
"""

from django.test import TestCase
from django.urls import reverse

from orders.models import Order
from orders.tests.factories import (
    OfflineOrderFactory,
    OrderFactory,
    RoleFactory,
    TeamOrderFactory,
    UserFactory,
)


def _staff():
    return UserFactory(profile_completed=True, roles=[RoleFactory(name="STAFF")])


def _detalle(order):
    return reverse("orders:detail_order", args=[order.pk])


class StaffLeeCualquierPedidoTests(TestCase):

    def setUp(self):
        self.staff = _staff()
        self.client.force_login(self.staff)

    def test_abre_un_pedido_de_equipo_ajeno(self):
        order = TeamOrderFactory()
        resp = self.client.get(_detalle(order))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["order"].pk, order.pk)

    def test_abre_un_pedido_personal_ajeno(self):
        order = OrderFactory()
        resp = self.client.get(_detalle(order))
        self.assertEqual(resp.status_code, 200)

    def test_abre_un_pedido_offline(self):
        order = OfflineOrderFactory()
        resp = self.client.get(_detalle(order))
        self.assertEqual(resp.status_code, 200)

    def test_no_se_le_ofrece_ninguna_transicion(self):
        order = TeamOrderFactory()
        resp = self.client.get(_detalle(order))
        self.assertEqual(resp.context["available_transitions"], [])
        self.assertNotContains(
            resp, reverse("orders:transition", args=[order.pk, "PENDING"])
        )

    def test_no_puede_cancelar_un_pedido_ajeno_por_post(self):
        order = TeamOrderFactory()
        self.client.post(reverse("orders:transition", args=[order.pk, "CANCELLED"]))
        order.refresh_from_db()
        self.assertEqual(order.status, "DRAFT")

    def test_no_ve_botones_de_edicion_en_un_pedido_editable_ajeno(self):
        # La plantilla muestra agregar/editar según `order.can_edit_general`,
        # que mira el estado del pedido y no quién lo está viendo.
        order = TeamOrderFactory()
        self.assertTrue(order.can_edit_general())
        resp = self.client.get(_detalle(order))
        self.assertNotContains(resp, reverse("orders:add_item_product_order", args=[order.pk]))
        self.assertNotContains(resp, reverse("orders:edit_order", args=[order.pk]))

    def test_si_el_pedido_es_suyo_sigue_pudiendo_editarlo(self):
        order = TeamOrderFactory(created_by=self.staff)
        resp = self.client.get(_detalle(order))
        self.assertContains(resp, reverse("orders:add_item_product_order", args=[order.pk]))

    def test_volver_lo_lleva_a_la_lista_de_administracion(self):
        # Se mira el contexto y no el HTML: el menú de STAFF ya enlaza esa lista,
        # así que buscar el href pasaría aunque "Volver" apuntara a otro lado.
        resp = self.client.get(_detalle(TeamOrderFactory()))
        self.assertEqual(resp.context["back_url"], reverse("orders:admin_order_list"))
        self.assertNotContains(resp, f'href="{reverse("orders:manage_orders")}"')


class StaffAbreLaListaDeAdministracionTests(TestCase):
    """El menú ya le mostraba "Administrar Pedidos"; la vista lo rechazaba."""

    def setUp(self):
        self.order = TeamOrderFactory()

    def _lista(self, user):
        self.client.force_login(user)
        return self.client.get(reverse("orders:admin_order_list"))

    def test_staff_abre_la_lista(self):
        resp = self._lista(_staff())
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, f"#{self.order.pk}")

    def test_staff_no_ve_las_acciones_que_siguen_siendo_de_admin(self):
        resp = self._lista(_staff())
        self.assertNotContains(resp, reverse("orders:offline_order_create"))
        self.assertNotContains(resp, reverse("orders:customer_list"))

    def test_la_fila_lleva_a_staff_al_detalle_que_si_puede_abrir(self):
        resp = self._lista(_staff())
        self.assertNotContains(
            resp, f'href="{reverse("orders:admin_order_detail", args=[self.order.pk])}"'
        )
        self.assertContains(resp, f'href="{_detalle(self.order)}"')

    def test_admin_conserva_sus_acciones_y_su_detalle(self):
        admin = UserFactory(profile_completed=True, roles=[RoleFactory(name="ADMIN")])
        resp = self._lista(admin)
        self.assertContains(resp, reverse("orders:offline_order_create"))
        self.assertContains(
            resp, f'href="{reverse("orders:admin_order_detail", args=[self.order.pk])}"'
        )

    def test_un_coach_sigue_sin_abrirla(self):
        coach = UserFactory(profile_completed=True, roles=[RoleFactory(name="COACH")])
        resp = self._lista(coach)
        self.assertEqual(resp.status_code, 302)


class LaLecturaNoSeAbreAOtrosRolesTests(TestCase):

    def test_un_atleta_sigue_sin_ver_un_pedido_ajeno(self):
        atleta = UserFactory(profile_completed=True, roles=[RoleFactory(name="ATHLETE")])
        self.client.force_login(atleta)
        resp = self.client.get(_detalle(TeamOrderFactory()))
        self.assertEqual(resp.status_code, 404)

    def test_el_dueno_sigue_volviendo_a_su_lista(self):
        coach = UserFactory(profile_completed=True, roles=[RoleFactory(name="HEADCOACH")])
        order = TeamOrderFactory(created_by=coach)
        self.client.force_login(coach)
        resp = self.client.get(_detalle(order))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, f'href="{reverse("orders:manage_orders")}"')
        self.assertContains(resp, reverse("orders:add_item_product_order", args=[order.pk]))

    def test_staff_sigue_sin_poder_editar_un_pedido_ajeno(self):
        """La edición filtra por `visible_for_user`, que no cambió."""
        staff = _staff()
        self.assertFalse(
            Order.objects.visible_for_user(staff).filter(pk=TeamOrderFactory().pk).exists()
        )

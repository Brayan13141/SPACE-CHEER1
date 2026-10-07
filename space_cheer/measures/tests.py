"""Pantalla de campos de medida (/measures/measures/fields/).

Regresión: los modales de editar/eliminar se renderizaban DENTRO del <tbody>.
El parser HTML saca esos <form> de la tabla vacíos y deja los campos asociados
solo por el puntero del parser; en cuanto base.html envuelve cada input
`required` para su hint "• obligatorio", el navegador recalcula el dueño y
name/slug/order salen del form. El POST llegaba sin ellos y nada se guardaba.
"""

from django.test import TestCase
from django.urls import reverse

from measures.models import MeasurementField
from orders.tests.factories import RoleFactory, UserFactory


class ManageFieldsTests(TestCase):

    def setUp(self):
        self.admin = UserFactory(profile_completed=True, roles=[RoleFactory(name="ADMIN")])
        self.client.force_login(self.admin)
        self.url = reverse("measures:manage_measurement_fields")
        self.campo = MeasurementField.objects.create(
            name="Estatura", slug="estatura", field_type="decimal", unit="cm", order=1,
        )

    def test_los_modales_con_formulario_quedan_fuera_de_la_tabla(self):
        html = self.client.get(self.url).content.decode()
        fin_tabla = html.index("</table>")
        for modal_id in (f'id="modalEditar{self.campo.id}"', f'id="modalEliminar{self.campo.id}"'):
            self.assertGreater(
                html.index(modal_id), fin_tabla,
                f"{modal_id} está dentro de la tabla: el parser deja su <form> vacío",
            )

    def test_editar_con_todos_los_campos_guarda(self):
        """Control: con el POST completo, la vista sí guarda."""
        resp = self.client.post(self.url, {
            "editar_medida": "", "field_id": self.campo.id,
            "name": "Estatura total", "slug": "estatura", "order": 1,
            "field_type": "decimal", "unit": "cm", "required": "on", "is_active": "on",
        })
        self.assertEqual(resp.status_code, 302)
        self.campo.refresh_from_db()
        self.assertEqual(self.campo.name, "Estatura total")

    def test_habilitar_con_la_clave_de_accion_reactiva_el_campo(self):
        self.campo.is_active = False
        self.campo.save()
        resp = self.client.post(self.url, {"habilitar_medida": "", "field_id": self.campo.id})
        self.assertEqual(resp.status_code, 302)
        self.campo.refresh_from_db()
        self.assertTrue(self.campo.is_active)

    def test_el_formulario_de_habilitar_no_depende_solo_del_nombre_del_boton(self):
        # sc-submit-guard.js deshabilita el botón al enviar y un botón
        # deshabilitado no viaja en el POST: la clave tiene que ir en un hidden.
        self.campo.is_active = False
        self.campo.save()
        html = self.client.get(self.url).content.decode()
        self.assertIn('<input type="hidden" name="habilitar_medida"', html)

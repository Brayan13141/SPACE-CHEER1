"""Detalle admin: el bloqueo de medidas deja de ser un paso escondido.

Aprobar el diseño solo CIERRA las medidas; producción exige además
`measurements_locked`, que se activa con una acción aparte. Desde el panel no se
veía que faltaba: "Enviar a Producción" estaba activo y fallaba al confirmarlo,
de a un error por vez, y "Bloquear definitivo" se ejecutaba sin confirmación.
"""

import shutil
import tempfile
from datetime import timedelta

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from orders.services.preconditions import next_step_requirements
from orders.tests.factories import (
    OrderDesignImageFactory,
    OrderItemFactory,
    ProductFactory,
    ProductWithMeasurementsFactory,
    RoleFactory,
    TeamOrderFactory,
    UserFactory,
)


def _pedido(status, producto, diseno_final=False, **kwargs):
    """Items primero, estado después: OrderItem.save() rechaza cambios a
    partir de DESIGN_APPROVED."""
    order = TeamOrderFactory(**kwargs)
    OrderItemFactory(order=order, product=producto)
    if diseno_final:
        OrderDesignImageFactory(order=order, is_final=True)
    order.status = status
    order._allow_status_change = True
    order.save()
    return order


class AdminDetalleBloqueoMedidasTests(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # TestCase no limpia MEDIA_ROOT: las imágenes de diseño van a un
        # directorio propio que se borra al terminar.
        cls._media = tempfile.mkdtemp()
        cls._media_override = override_settings(MEDIA_ROOT=cls._media)
        cls._media_override.enable()

    @classmethod
    def tearDownClass(cls):
        cls._media_override.disable()
        shutil.rmtree(cls._media, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.admin = UserFactory(
            profile_completed=True, roles=[RoleFactory(name="ADMIN")]
        )
        self.client.force_login(self.admin)
        hoy = timezone.localdate()
        self.listo = {
            "first_payment_date": hoy,
            "uniform_delivery_date": hoy + timedelta(days=30),
            "measurements_due_date": hoy + timedelta(days=7),
        }

    def _get(self, order):
        resp = self.client.get(reverse("orders:admin_order_detail", args=[order.pk]))
        self.assertEqual(resp.status_code, 200)
        return resp

    def test_lista_lo_que_falta_para_producir(self):
        order = _pedido(
            "DESIGN_APPROVED", ProductWithMeasurementsFactory(),
            measurements_open=False, **self.listo,
        )
        resp = self._get(order)

        codigos = {r.code for r in resp.context["next_requirements"]}
        self.assertIn("MEASURES_NOT_LOCKED", codigos)
        self.assertContains(resp, "Falta bloquear las medidas")

    def test_enviar_a_produccion_queda_deshabilitado_si_falta_algo(self):
        order = _pedido(
            "DESIGN_APPROVED", ProductWithMeasurementsFactory(),
            measurements_open=False, **self.listo,
        )
        resp = self._get(order)

        self.assertTrue(resp.context["in_production_blocked"])
        html = resp.content.decode()
        boton = html[html.index('id="btnInProduction"'):]
        boton = boton[:boton.index(">")]
        self.assertIn("disabled", boton)

    def test_enviar_a_produccion_activo_cuando_no_falta_nada(self):
        order = _pedido(
            "DESIGN_APPROVED", ProductWithMeasurementsFactory(),
            measurements_open=False, measurements_locked=True,
            diseno_final=True, **self.listo,
        )
        resp = self._get(order)

        self.assertEqual(resp.context["next_requirements"], [])
        self.assertFalse(resp.context["in_production_blocked"])
        html = resp.content.decode()
        boton = html[html.index('id="btnInProduction"'):]
        boton = boton[:boton.index(">")]
        self.assertNotIn("disabled", boton)

    def test_bloquear_definitivo_pide_confirmacion(self):
        order = _pedido(
            "DESIGN_APPROVED", ProductWithMeasurementsFactory(),
            measurements_open=False, **self.listo,
        )
        html = self._get(order).content.decode()

        url_bloqueo = reverse("orders:lock_measurements", args=[order.pk])
        # El POST de bloqueo vive dentro del modal, no en el botón de la tarjeta.
        self.assertIn('data-bs-target="#modalLockMeasurements"', html)
        self.assertGreater(
            html.index(f'action="{url_bloqueo}"'),
            html.index('id="modalLockMeasurements"'),
        )

    def test_explica_que_significa_cada_estado_de_medidas(self):
        abiertas = _pedido("PENDING", ProductWithMeasurementsFactory())
        self.assertContains(self._get(abiertas), "Las familias y el coach todavía pueden capturar")

        cerradas = _pedido(
            "DESIGN_APPROVED", ProductWithMeasurementsFactory(),
            measurements_open=False, **self.listo,
        )
        self.assertContains(self._get(cerradas), "Para enviar a producción hay que bloquearlas")

        bloqueadas = _pedido(
            "DESIGN_APPROVED", ProductWithMeasurementsFactory(),
            measurements_open=False, measurements_locked=True, **self.listo,
        )
        self.assertContains(self._get(bloqueadas), "Ya nadie puede corregir una medida")


class RequisitosHaciaUnEstadoTests(TestCase):

    def test_pending_sin_diseno_se_evalua_contra_produccion(self):
        """Sin diseño, PENDING salta directo a IN_PRODUCTION: el botón tiene que
        juzgarse contra ese salto, no contra la aprobación de diseño."""
        order = _pedido("PENDING", ProductFactory(usage_type="GLOBAL"))

        codigos = {
            r.code for r in next_step_requirements(order, to_status="IN_PRODUCTION")
        }
        self.assertIn("NO_FIRST_PAYMENT", codigos)
        self.assertNotIn("DESIGN_NOT_APPROVED", codigos)

    def test_pending_con_diseno_no_salta_la_aprobacion(self):
        """Espeja el rechazo de _validate_to_in_production: con diseño, el
        botón de producción no puede verse habilitado desde PENDING."""
        order = _pedido("PENDING", ProductWithMeasurementsFactory())

        codigos = {
            r.code for r in next_step_requirements(order, to_status="IN_PRODUCTION")
        }
        self.assertIn("DESIGN_NOT_APPROVED", codigos)

"""Qué falta para que un pedido avance, y de quién depende cada cosa.

El head coach veía un pedido detenido sin ninguna señal de qué esperaba ni de
quién: las validaciones existían, pero solo hablaban cuando alguien ya había
intentado avanzar, y de a un error por vez.
"""

from django.test import TestCase
from django.utils import timezone

from orders.services.preconditions import (
    OWNER_ADMIN,
    OWNER_COACH,
    OWNER_TALLER,
    next_step_requirements,
)
from orders.tests.factories import (
    OrderItemFactory,
    ProductFactory,
    TeamOrderFactory,
)


def codigos(order):
    return {r.code for r in next_step_requirements(order)}


def por_codigo(order, code):
    return next(r for r in next_step_requirements(order) if r.code == code)


class NextStepRequirementsTests(TestCase):

    def _pedido(self, status, productos=(), **kwargs):
        """Crea la orden en DRAFT, le agrega los items y recién ahí la mueve.

        OrderItem.save() rechaza cualquier cambio a partir de DESIGN_APPROVED,
        así que el orden importa: primero el contenido, después el estado.
        """
        cerrada = kwargs.pop("closed", False)
        order = TeamOrderFactory(**kwargs)
        for product in productos:
            OrderItemFactory(order=order, product=product)
        order.status = status
        # `closed` viaja junto con el estado: una orden cerrada tiene que estar
        # ya en DELIVERED o CANCELLED, así que no puede fijarse al crearla.
        order.closed = cerrada
        order._allow_status_change = True
        order.save()
        return order

    def test_un_estado_final_no_pide_nada(self):
        for status in ("DELIVERED", "CANCELLED"):
            order = self._pedido(status, closed=True)
            self.assertEqual(next_step_requirements(order), [])

    def test_reporta_todos_los_pendientes_de_una_vez(self):
        """El punto del cambio: no de a un error por intento."""
        product = ProductFactory(
            product_type="UNIFORM", usage_type="GLOBAL", size_strategy="NONE",
        )
        order = self._pedido("DESIGN_APPROVED", productos=[product])

        faltantes = codigos(order)
        self.assertIn("NO_DELIVERY_DATE", faltantes)
        self.assertIn("NO_FIRST_PAYMENT", faltantes)
        self.assertGreaterEqual(len(faltantes), 2)

    def test_el_bloqueo_de_medidas_se_anuncia_antes_de_intentarlo(self):
        from orders.tests.factories import ProductWithMeasurementsFactory

        product = ProductWithMeasurementsFactory(product_type="UNIFORM")
        order = self._pedido(
            "DESIGN_APPROVED", productos=[product], measurements_locked=False,
        )
        order.measurements_due_date = timezone.now().date()
        order.uniform_delivery_date = timezone.now().date()
        order.first_payment_date = timezone.now()
        order.save(update_fields=[
            "measurements_due_date", "uniform_delivery_date", "first_payment_date",
        ])

        self.assertIn("MEASURES_NOT_LOCKED", codigos(order))

    def test_el_bloqueo_explica_que_es_definitivo(self):
        """Sin el porqué, el aviso invita a hacer clic sin entender."""
        from orders.tests.factories import ProductWithMeasurementsFactory

        product = ProductWithMeasurementsFactory(product_type="UNIFORM")
        order = self._pedido(
            "DESIGN_APPROVED", productos=[product], measurements_locked=False,
        )

        req = por_codigo(order, "MEASURES_NOT_LOCKED")
        self.assertIn("definitiva", req.hint)
        self.assertEqual(req.owner, OWNER_ADMIN)

    def test_distingue_lo_del_coach_de_lo_de_administracion(self):
        product = ProductFactory(
            product_type="UNIFORM", usage_type="GLOBAL", size_strategy="NONE",
        )
        order = self._pedido("DESIGN_APPROVED", productos=[product])

        pago = por_codigo(order, "NO_FIRST_PAYMENT")
        self.assertEqual(pago.owner, OWNER_ADMIN)
        self.assertFalse(pago.is_mine)
        self.assertEqual(pago.owner_label, "Lo resuelve administración")

    def test_las_etapas_pendientes_son_del_taller(self):
        from production.models import ProductionJob, ProductionStage, ProductionTask

        product = ProductFactory(
            product_type="UNIFORM", usage_type="GLOBAL", size_strategy="NONE",
        )
        order = self._pedido("IN_PRODUCTION", productos=[product])
        item = order.items.first()
        job = ProductionJob.objects.create(order=order)
        stage = ProductionStage.objects.create(
            name="Corte", slug="corte-test", display_order=1,
        )
        ProductionTask.objects.create(job=job, order_item=item, stage=stage)

        req = por_codigo(order, "PRODUCTION_PENDING")
        self.assertEqual(req.owner, OWNER_TALLER)
        self.assertIn("1 etapa", req.message)

    def test_un_pedido_sin_pendientes_devuelve_lista_vacia(self):
        product = ProductFactory(
            product_type="OTHER", usage_type="GLOBAL", size_strategy="NONE",
        )
        order = self._pedido("DESIGN_APPROVED", productos=[product])
        order.first_payment_date = timezone.now()
        order.save(update_fields=["first_payment_date"])

        self.assertEqual(next_step_requirements(order), [])

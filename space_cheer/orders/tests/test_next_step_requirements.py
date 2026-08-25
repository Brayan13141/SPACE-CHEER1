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


class RequirementVisibilityTests(TestCase):
    """Cómo se organiza Space Cheer por dentro no es asunto del cliente.

    El cliente ve lo que le toca a él —tiene que poder actuar sobre ello— y del
    resto solo sabe que el pedido está en curso.
    """

    def setUp(self):
        from accounts.models import Role
        from orders.tests.factories import ProductFactory, UserFactory

        self.product = ProductFactory(
            product_type="UNIFORM", usage_type="GLOBAL", size_strategy="NONE",
        )
        self.order = TeamOrderFactory()
        OrderItemFactory(order=self.order, product=self.product)
        self.order.status = "DESIGN_APPROVED"
        self.order._allow_status_change = True
        self.order.save()

        self.cliente = self.order.owner_team.coach
        self.admin = UserFactory(username="admin_vis")
        self.admin.roles.add(Role.objects.get_or_create(name="ADMIN")[0])
        self.staff = UserFactory(username="staff_vis")
        self.staff.roles.add(Role.objects.get_or_create(name="STAFF")[0])

    def test_el_cliente_no_ve_los_pendientes_de_administracion(self):
        from orders.services.preconditions import visible_requirements

        visibles, hay_internos = visible_requirements(self.order, self.cliente)

        self.assertTrue(hay_internos)
        self.assertEqual(visibles, [])
        self.assertNotIn("NO_FIRST_PAYMENT", {r.code for r in visibles})

    def test_administracion_los_ve_todos(self):
        from orders.services.preconditions import (
            next_step_requirements, visible_requirements,
        )

        for usuario in (self.admin, self.staff):
            visibles, hay_internos = visible_requirements(self.order, usuario)
            self.assertFalse(hay_internos)
            self.assertEqual(
                {r.code for r in visibles},
                {r.code for r in next_step_requirements(self.order)},
            )

    def test_el_cliente_si_ve_lo_suyo(self):
        """Ocultarle sus propios pendientes lo dejaría sin saber qué hacer."""
        from orders.services.preconditions import (
            OWNER_COACH, OrderBlockingIssue, visible_requirements,
        )
        from unittest.mock import patch

        propio = OrderBlockingIssue(
            code="ALGO_MIO", message="Falta algo tuyo", owner=OWNER_COACH,
        )
        with patch(
            "orders.services.preconditions.next_step_requirements",
            return_value=[propio],
        ):
            visibles, hay_internos = visible_requirements(self.order, self.cliente)

        self.assertEqual([r.code for r in visibles], ["ALGO_MIO"])
        self.assertFalse(hay_internos)

    def test_el_mensaje_generico_no_filtra_nada_interno(self):
        from orders.services.preconditions import GENERIC_INTERNAL_MESSAGE

        texto = GENERIC_INTERNAL_MESSAGE.lower()
        for palabra in ("pago", "medida", "bloque", "etapa", "taller", "producción"):
            self.assertNotIn(palabra, texto)

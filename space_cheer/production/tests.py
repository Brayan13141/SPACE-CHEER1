from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.utils import timezone

from orders.tests.factories import (
    OrderFactory,
    OrderItemFactory,
    ProductFactory,
    UserFactory,
)
from orders.services.state import OrderStateService
from production.models import (
    ProductionStage,
    ProductStageConfig,
    ProductionRole,
    OperarioRoleAssignment,
    ProductionJob,
    ProductionTask,
)
from production.services import ProductionJobService


# ---------------------------------------------------------------------------
# ProductionStage
# ---------------------------------------------------------------------------

class ProductionStageTests(TestCase):

    def test_stages_ordered_by_display_order(self):
        """Las etapas se devuelven ordenadas por display_order"""
        ProductionStage.objects.create(name="Envío", slug="envio", display_order=9)
        ProductionStage.objects.create(name="Diseño", slug="diseno", display_order=1)
        names = list(ProductionStage.objects.values_list("name", flat=True))
        self.assertEqual(names, ["Diseño", "Envío"])

    def test_stage_slug_is_unique(self):
        """Dos etapas no pueden tener el mismo slug"""
        from django.db import IntegrityError
        ProductionStage.objects.create(name="Diseño", slug="diseno", display_order=1)
        with self.assertRaises(IntegrityError):
            ProductionStage.objects.create(name="Diseño 2", slug="diseno", display_order=2)


# ---------------------------------------------------------------------------
# ProductStageConfig
# ---------------------------------------------------------------------------

class ProductStageConfigTests(TestCase):

    def test_unique_product_stage_pair(self):
        """Un producto no puede tener la misma etapa configurada dos veces"""
        from django.db import IntegrityError
        product = ProductFactory()
        stage = ProductionStage.objects.create(name="Diseño", slug="diseno", display_order=1)
        ProductStageConfig.objects.create(product=product, stage=stage, display_order=1)
        with self.assertRaises(IntegrityError):
            ProductStageConfig.objects.create(product=product, stage=stage, display_order=2)


# ---------------------------------------------------------------------------
# ProductionJob
# ---------------------------------------------------------------------------

class ProductionJobTests(TestCase):

    def test_job_is_onetoone_with_order(self):
        """Solo puede existir un ProductionJob por orden"""
        from django.db import IntegrityError
        order = OrderFactory()
        ProductionJob.objects.create(order=order)
        with self.assertRaises(IntegrityError):
            ProductionJob.objects.create(order=order)

    def test_job_is_not_urgent_by_default(self):
        order = OrderFactory()
        job = ProductionJob.objects.create(order=order)
        self.assertFalse(job.is_urgent)


# ---------------------------------------------------------------------------
# ProductionTask
# ---------------------------------------------------------------------------

class ProductionTaskTests(TestCase):

    def test_task_unique_per_job_item_stage(self):
        """Una tarea (job, item, etapa) no puede duplicarse"""
        from django.db import IntegrityError
        order = OrderFactory()
        item = OrderItemFactory(order=order)
        job = ProductionJob.objects.create(order=order)
        stage = ProductionStage.objects.create(name="Diseño", slug="diseno", display_order=1)
        ProductionTask.objects.create(
            job=job, order_item=item, stage=stage,
            status="PENDING", started_at=timezone.now()
        )
        with self.assertRaises(IntegrityError):
            ProductionTask.objects.create(
                job=job, order_item=item, stage=stage,
                status="PENDING", started_at=timezone.now()
            )

    def test_task_default_status_is_pending(self):
        order = OrderFactory()
        item = OrderItemFactory(order=order)
        job = ProductionJob.objects.create(order=order)
        stage = ProductionStage.objects.create(name="Diseño", slug="diseno", display_order=1)
        task = ProductionTask.objects.create(
            job=job, order_item=item, stage=stage, started_at=timezone.now()
        )
        self.assertEqual(task.status, "PENDING")


# ---------------------------------------------------------------------------
# OperarioRoleAssignment
# ---------------------------------------------------------------------------

class OperarioRoleAssignmentTests(TestCase):

    def test_unique_user_role_pair(self):
        """Un operario no puede tener asignado el mismo ProductionRole dos veces"""
        from django.db import IntegrityError
        user = UserFactory()
        assigner = UserFactory()
        prod_role = ProductionRole.objects.create(name="Diseñador", created_by=assigner)
        OperarioRoleAssignment.objects.create(user=user, role=prod_role, assigned_by=assigner)
        with self.assertRaises(IntegrityError):
            OperarioRoleAssignment.objects.create(user=user, role=prod_role, assigned_by=assigner)


# ---------------------------------------------------------------------------
# ProductionJobService.create_for_order
# ---------------------------------------------------------------------------

class ProductionJobServiceCreateTests(TestCase):

    def setUp(self):
        self.order = OrderFactory()
        self.item = OrderItemFactory(order=self.order)
        self.stage1 = ProductionStage.objects.create(name="Diseño", slug="diseno", display_order=1)
        self.stage2 = ProductionStage.objects.create(name="Corte", slug="corte", display_order=5)
        ProductStageConfig.objects.create(
            product=self.item.product, stage=self.stage1, display_order=1
        )
        ProductStageConfig.objects.create(
            product=self.item.product, stage=self.stage2, display_order=2
        )

    def test_create_for_order_creates_job(self):
        """create_for_order debe crear un ProductionJob para la orden"""
        ProductionJobService.create_for_order(self.order)
        self.assertTrue(ProductionJob.objects.filter(order=self.order).exists())

    def test_create_for_order_creates_tasks_per_item_per_stage(self):
        """create_for_order crea una task por cada (OrderItem × ProductionStage)"""
        ProductionJobService.create_for_order(self.order)
        job = ProductionJob.objects.get(order=self.order)
        self.assertEqual(job.tasks.count(), 2)

    def test_create_for_order_tasks_started_at_equals_job_created_at(self):
        """Todas las tasks deben tener started_at = job.created_at"""
        ProductionJobService.create_for_order(self.order)
        job = ProductionJob.objects.get(order=self.order)
        for task in job.tasks.all():
            self.assertEqual(task.started_at, job.created_at)

    def test_create_for_order_tasks_are_all_pending(self):
        """Todas las tasks creadas deben tener status PENDING"""
        ProductionJobService.create_for_order(self.order)
        job = ProductionJob.objects.get(order=self.order)
        statuses = list(job.tasks.values_list("status", flat=True))
        self.assertTrue(all(s == "PENDING" for s in statuses))

    def test_create_for_order_logs_warning_for_product_without_stages(self, ):
        """Si un producto no tiene etapas configuradas, se loguea advertencia sin error"""
        item_no_stages = OrderItemFactory(order=self.order)
        # item_no_stages.product no tiene ProductStageConfig
        import logging
        with self.assertLogs("production.services", level="WARNING") as cm:
            ProductionJobService.create_for_order(self.order)
        self.assertTrue(
            any("sin etapas" in msg.lower() or "no stages" in msg.lower() or str(item_no_stages.product_id) in msg for msg in cm.output)
        )

    def test_create_for_order_multiple_items_each_get_tasks(self):
        """Cada OrderItem recibe sus propias tasks"""
        item2 = OrderItemFactory(order=self.order)
        ProductStageConfig.objects.create(
            product=item2.product, stage=self.stage1, display_order=1
        )
        ProductionJobService.create_for_order(self.order)
        job = ProductionJob.objects.get(order=self.order)
        # item1: 2 stages, item2: 1 stage = 3 tasks total
        self.assertEqual(job.tasks.count(), 3)


# ---------------------------------------------------------------------------
# ProductionJobService.complete_task
# ---------------------------------------------------------------------------

class ProductionJobServiceCompleteTaskTests(TestCase):

    def setUp(self):
        self.order = OrderFactory()
        self.item = OrderItemFactory(order=self.order)
        self.stage = ProductionStage.objects.create(
            name="Diseño", slug="diseno", display_order=1
        )
        ProductStageConfig.objects.create(
            product=self.item.product, stage=self.stage, display_order=1
        )
        ProductionJobService.create_for_order(self.order)
        self.job = ProductionJob.objects.get(order=self.order)
        self.task = self.job.tasks.first()
        self.user = UserFactory()
        # Silencia Celery en todos los tests salvo el de notificación
        patcher = patch("production.services.notify_production_stage_complete")
        self.mock_notify = patcher.start()
        self.addCleanup(patcher.stop)

    def test_complete_task_sets_status_completed(self):
        """complete_task debe cambiar status a COMPLETED"""
        ProductionJobService.complete_task(
            self.task, self.user, started_at=self.task.started_at, notes=""
        )
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, "COMPLETED")

    def test_complete_task_sets_completed_by(self):
        """complete_task debe registrar quién completó la tarea"""
        ProductionJobService.complete_task(
            self.task, self.user, started_at=self.task.started_at, notes=""
        )
        self.task.refresh_from_db()
        self.assertEqual(self.task.completed_by, self.user)

    def test_complete_task_sets_completed_at(self):
        """complete_task debe registrar cuándo se completó"""
        ProductionJobService.complete_task(
            self.task, self.user, started_at=self.task.started_at, notes=""
        )
        self.task.refresh_from_db()
        self.assertIsNotNone(self.task.completed_at)

    def test_complete_task_saves_notes(self):
        """complete_task debe guardar las notas opcionales"""
        ProductionJobService.complete_task(
            self.task, self.user, started_at=self.task.started_at, notes="Revisado OK"
        )
        self.task.refresh_from_db()
        self.assertEqual(self.task.notes, "Revisado OK")

    def test_complete_task_fires_celery_notification(self):
        """complete_task debe disparar notify_production_stage_complete.delay(task.id)"""
        ProductionJobService.complete_task(
            self.task, self.user, started_at=self.task.started_at, notes=""
        )
        self.mock_notify.delay.assert_called_once_with(self.task.id)


# ---------------------------------------------------------------------------
# C2 — OrderStateService hook: IN_PRODUCTION crea ProductionJob
# ---------------------------------------------------------------------------

class OrderStateServiceProductionHookTests(TestCase):

    @patch("production.services.notify_production_stage_complete")
    @patch("orders.services.state.OrderNotificationService.notify_production_started")
    @patch("production.services.ProductionJobService.create_for_order")
    def test_transition_to_in_production_calls_create_for_order(
        self, mock_create, mock_notify_order, mock_notify_celery
    ):
        """Al pasar a IN_PRODUCTION, _post_transition_hooks debe llamar create_for_order"""
        order = OrderFactory()
        user = UserFactory()
        OrderStateService._post_transition_hooks(order, "DESIGN_APPROVED", "IN_PRODUCTION", user)
        mock_create.assert_called_once_with(order)

    @patch("production.services.notify_production_stage_complete")
    @patch("orders.services.state.OrderNotificationService.notify_production_started")
    @patch("production.services.ProductionJobService.create_for_order")
    def test_transition_to_other_status_does_not_call_create_for_order(
        self, mock_create, mock_notify_order, mock_notify_celery
    ):
        """En transiciones que no son IN_PRODUCTION, create_for_order no se llama"""
        order = OrderFactory()
        user = UserFactory()
        OrderStateService._post_transition_hooks(order, "PENDING", "DESIGN_APPROVED", user)
        mock_create.assert_not_called()

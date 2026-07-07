"""
Tests de la máquina de estados de ProductionJob.

PENDING → IN_PROGRESS ⇄ PAUSED
   ↓            ↓          ↓
CANCELLED  COMPLETED   CANCELLED

Reglas:
- El estado NUNCA se cambia directamente: siempre vía ProductionJobStateService.
- COMPLETED exige que todas las tasks del job estén completadas.
- PAUSED/CANCELLED (y reanudar desde PAUSED) son acciones manuales de ADMIN.
- complete_task integra la máquina: arranca el job (PENDING→IN_PROGRESS) y lo
  cierra (→COMPLETED) automáticamente; bloquea si el job está PAUSED/CANCELLED.
"""

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.utils import timezone

from orders.tests.factories import (
    OrderFactory,
    OrderItemFactory,
    RoleFactory,
    UserFactory,
)
from production.models import (
    ProductionJob,
    ProductionStage,
    ProductionTask,
    ProductStageConfig,
)
from production.services import ProductionJobService
from production.state import ProductionJobStateService


def _admin_user():
    return UserFactory(roles=[RoleFactory(name="ADMIN")])


def _operario_user():
    return UserFactory(roles=[RoleFactory(name="OPERARIO")])


class ProductionJobStateMachineBase(TestCase):
    def setUp(self):
        self.order = OrderFactory()
        self.item = OrderItemFactory(order=self.order)
        self.stage1 = ProductionStage.objects.create(
            name="Diseño", slug="diseno", display_order=1
        )
        self.stage2 = ProductionStage.objects.create(
            name="Corte", slug="corte", display_order=2
        )
        ProductStageConfig.objects.create(
            product=self.item.product, stage=self.stage1, display_order=1
        )
        ProductStageConfig.objects.create(
            product=self.item.product, stage=self.stage2, display_order=2
        )
        self.job = ProductionJobService.create_for_order(self.order)
        self.admin = _admin_user()
        self.operario = _operario_user()

    def _complete_all_tasks(self):
        self.job.tasks.update(
            status=ProductionTask.Status.COMPLETED, completed_at=timezone.now()
        )


class ProductionJobStatusModelTests(ProductionJobStateMachineBase):
    def test_default_status_is_pending(self):
        self.assertEqual(self.job.status, ProductionJob.Status.PENDING)

    def test_direct_status_change_raises(self):
        self.job.status = ProductionJob.Status.IN_PROGRESS
        with self.assertRaises(ValidationError):
            self.job.save()


class ProductionJobStateServiceTests(ProductionJobStateMachineBase):
    def test_pending_to_in_progress_ok(self):
        ProductionJobStateService.transition(
            self.job, ProductionJob.Status.IN_PROGRESS
        )
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, ProductionJob.Status.IN_PROGRESS)

    def test_pending_to_paused_not_allowed(self):
        with self.assertRaises(ValidationError) as ctx:
            ProductionJobStateService.transition(
                self.job, ProductionJob.Status.PAUSED, user=self.admin
            )
        self.assertIn("PENDING", str(ctx.exception))
        self.assertIn("PAUSED", str(ctx.exception))

    def test_in_progress_to_paused_and_resume(self):
        ProductionJobStateService.transition(
            self.job, ProductionJob.Status.IN_PROGRESS
        )
        ProductionJobStateService.transition(
            self.job, ProductionJob.Status.PAUSED, user=self.admin
        )
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, ProductionJob.Status.PAUSED)

        ProductionJobStateService.transition(
            self.job, ProductionJob.Status.IN_PROGRESS, user=self.admin
        )
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, ProductionJob.Status.IN_PROGRESS)

    def test_completed_requires_all_tasks_done(self):
        ProductionJobStateService.transition(
            self.job, ProductionJob.Status.IN_PROGRESS
        )
        with self.assertRaises(ValidationError):
            ProductionJobStateService.transition(
                self.job, ProductionJob.Status.COMPLETED
            )

    def test_completed_sets_completed_at(self):
        ProductionJobStateService.transition(
            self.job, ProductionJob.Status.IN_PROGRESS
        )
        self._complete_all_tasks()
        ProductionJobStateService.transition(
            self.job, ProductionJob.Status.COMPLETED
        )
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, ProductionJob.Status.COMPLETED)
        self.assertIsNotNone(self.job.completed_at)

    def test_cancelled_is_terminal(self):
        ProductionJobStateService.transition(
            self.job, ProductionJob.Status.CANCELLED, user=self.admin
        )
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, ProductionJob.Status.CANCELLED)
        with self.assertRaises(ValidationError):
            ProductionJobStateService.transition(
                self.job, ProductionJob.Status.IN_PROGRESS, user=self.admin
            )

    def test_pause_requires_admin(self):
        ProductionJobStateService.transition(
            self.job, ProductionJob.Status.IN_PROGRESS
        )
        with self.assertRaises(PermissionDenied):
            ProductionJobStateService.transition(
                self.job, ProductionJob.Status.PAUSED, user=self.operario
            )

    def test_cancel_requires_admin(self):
        with self.assertRaises(PermissionDenied):
            ProductionJobStateService.transition(
                self.job, ProductionJob.Status.CANCELLED, user=self.operario
            )

    def test_can_transition(self):
        self.assertTrue(
            ProductionJobStateService.can_transition(
                self.job, ProductionJob.Status.IN_PROGRESS
            )
        )
        self.assertFalse(
            ProductionJobStateService.can_transition(
                self.job, ProductionJob.Status.COMPLETED
            )
        )


class CompleteTaskStateIntegrationTests(ProductionJobStateMachineBase):
    def _task(self, stage):
        return self.job.tasks.get(stage=stage)

    def test_first_completed_task_starts_job(self):
        ProductionJobService.complete_task(
            self._task(self.stage1), self.operario, started_at=timezone.now()
        )
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, ProductionJob.Status.IN_PROGRESS)

    def test_all_tasks_completed_closes_job(self):
        ProductionJobService.complete_task(
            self._task(self.stage1), self.operario, started_at=timezone.now()
        )
        ProductionJobService.complete_task(
            self._task(self.stage2), self.operario, started_at=timezone.now()
        )
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, ProductionJob.Status.COMPLETED)
        self.assertIsNotNone(self.job.completed_at)

    def test_complete_task_blocked_when_job_paused(self):
        ProductionJobStateService.transition(
            self.job, ProductionJob.Status.IN_PROGRESS
        )
        ProductionJobStateService.transition(
            self.job, ProductionJob.Status.PAUSED, user=self.admin
        )
        with self.assertRaises(ValidationError):
            ProductionJobService.complete_task(
                self._task(self.stage1), self.operario, started_at=timezone.now()
            )

    def test_complete_task_blocked_when_job_cancelled(self):
        ProductionJobStateService.transition(
            self.job, ProductionJob.Status.CANCELLED, user=self.admin
        )
        with self.assertRaises(ValidationError):
            ProductionJobService.complete_task(
                self._task(self.stage1), self.operario, started_at=timezone.now()
            )

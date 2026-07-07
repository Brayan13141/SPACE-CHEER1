"""
Máquina de estados de ProductionJob.

PENDING → IN_PROGRESS ⇄ PAUSED
   ↓            ↓          ↓
CANCELLED  COMPLETED   CANCELLED

El estado nunca se cambia directamente sobre el modelo: siempre a través de
ProductionJobStateService.transition() (mismo patrón que OrderStateService).
"""

import logging

from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone

logger = logging.getLogger(__name__)


class ProductionJobStateService:
    """Transiciones de estado de ProductionJob con guards, permisos y logging."""

    @classmethod
    def can_transition(cls, job, to_status):
        """Verifica si la transición está permitida desde el estado actual."""
        from production.models import ProductionJob

        return to_status in ProductionJob.ALLOWED_TRANSITIONS.get(job.status, [])

    @classmethod
    def transition(cls, job, to_status, user=None, notes=""):
        """
        Ejecuta una transición de estado del job.

        - PENDING→IN_PROGRESS y →COMPLETED pueden ser automáticas (user=None,
          disparadas por complete_task).
        - PAUSED, CANCELLED y reanudar desde PAUSED son acciones manuales que
          requieren usuario ADMIN.
        - COMPLETED exige que todas las tasks del job estén completadas y
          setea completed_at.
        """
        from production.models import ProductionJob, ProductionTask

        if not cls.can_transition(job, to_status):
            raise ValidationError(
                f"Transición no permitida en el job #{job.pk}: "
                f"{job.status} → {to_status}."
            )

        if cls._is_manual(job, to_status) and not cls._is_admin(user):
            raise PermissionDenied(
                f"Solo un administrador puede cambiar el job #{job.pk} "
                f"a {to_status}."
            )

        if to_status == ProductionJob.Status.COMPLETED:
            pending = (
                ProductionTask.objects.filter(job=job)
                .exclude(status=ProductionTask.Status.COMPLETED)
                .count()
            )
            if pending:
                raise ValidationError(
                    f"No se puede completar el job #{job.pk}: "
                    f"quedan {pending} tarea(s) sin completar."
                )

        from_status = job.status
        job.status = to_status
        update_fields = ["status"]
        if to_status == ProductionJob.Status.COMPLETED and job.completed_at is None:
            job.completed_at = timezone.now()
            update_fields.append("completed_at")

        job._allow_status_change = True
        job.save(update_fields=update_fields)

        logger.info(
            "ProductionJob #%s: %s → %s (user=%s)%s",
            job.pk,
            from_status,
            to_status,
            user or "system",
            f" — {notes}" if notes else "",
        )
        return job

    @staticmethod
    def _is_manual(job, to_status):
        """Pausar, cancelar y reanudar desde pausa son acciones manuales."""
        from production.models import ProductionJob

        return (
            to_status in (ProductionJob.Status.PAUSED, ProductionJob.Status.CANCELLED)
            or job.status == ProductionJob.Status.PAUSED
        )

    @staticmethod
    def _is_admin(user):
        if user is None:
            return False
        return user.is_superuser or user.roles.filter(name="ADMIN").exists()

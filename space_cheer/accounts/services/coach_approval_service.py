import logging
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


class CoachApprovalService:
    """Ciclo de aprobación de HEADCOACH.

    Un HEADCOACH se auto-registra y queda is_active=False hasta que un ADMIN
    lo aprueba. El COACH NO pasa por aquí (lo agrega un HEADCOACH ya aprobado).
    """

    @staticmethod
    def submit_headcoach(user):
        """Desactiva al usuario recién registrado como HEADCOACH (superusers exentos)."""
        if user.is_superuser:
            logger.info("HEADCOACH %s es superusuario, omitiendo aprobación", user.id)
            return user
        user.is_active = False
        user.save(update_fields=["is_active"])
        logger.info("HEADCOACH %s enviado a aprobación (is_active=False)", user.id)
        return user

    @staticmethod
    @transaction.atomic
    def approve_headcoach(coachprofile, by):
        """Activa al usuario, marca el CoachProfile APPROVED y dispara el email de aviso."""
        from accounts.tasks import notify_headcoach_approved

        user = coachprofile.user
        coachprofile.approval_status = coachprofile.APPROVED
        coachprofile.rejection_reason = ""
        coachprofile.approved_at = timezone.now()
        coachprofile.save(
            update_fields=["approval_status", "rejection_reason", "approved_at"]
        )
        user.is_active = True
        user.save(update_fields=["is_active"])
        logger.info("HEADCOACH %s aprobado por %s", user.id, getattr(by, "id", None))
        notify_headcoach_approved.delay(user.id)
        return coachprofile

    @staticmethod
    @transaction.atomic
    def reject_headcoach(coachprofile, by, reason=""):
        """Marca el CoachProfile REJECTED con el motivo dado; el usuario queda inactivo."""
        user = coachprofile.user
        coachprofile.approval_status = coachprofile.REJECTED
        coachprofile.rejection_reason = reason
        coachprofile.save(update_fields=["approval_status", "rejection_reason"])
        user.is_active = False
        user.save(update_fields=["is_active"])
        logger.info("HEADCOACH %s rechazado por %s", user.id, getattr(by, "id", None))
        return coachprofile

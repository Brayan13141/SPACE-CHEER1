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
        user.is_active = False
        user.save(update_fields=["is_active"])
        logger.info("HEADCOACH %s enviado a aprobación (is_active=False)", user.id)
        return user

    @staticmethod
    @transaction.atomic
    def approve_headcoach(coachprofile, by):
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
        user = coachprofile.user
        coachprofile.approval_status = coachprofile.REJECTED
        coachprofile.rejection_reason = reason
        coachprofile.save(update_fields=["approval_status", "rejection_reason"])
        user.is_active = False
        user.save(update_fields=["is_active"])
        logger.info("HEADCOACH %s rechazado por %s", user.id, getattr(by, "id", None))
        return coachprofile

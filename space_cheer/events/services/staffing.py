# events/services/staffing.py
"""Staff externo sin cuenta: enlace de la organización, revisión, gafete,
puerta y retención de datos personales."""

import datetime
import logging
import secrets

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from events import staff_tokens
from events.models import (
    Event,
    EventOrganization,
    EventStaffAssignment,
    StaffAccessLog,
    StaffMember,
)

logger = logging.getLogger(__name__)

_CLOSED_EVENT_STATUSES = (Event.STATUS_CANCELLED, Event.STATUS_COMPLETED)
_EDITABLE_FIELDS = ('full_name', 'phone', 'photo', 'credential', 'role', 'shift')


def _delete_file_on_commit(storage, name):
    """Borra un archivo solo si la transacción se confirma."""
    if not name:
        return

    def _delete():
        try:
            storage.delete(name)
        except Exception:
            logger.exception('No se pudo borrar el archivo %s', name)

    transaction.on_commit(_delete)


class ExternalStaffService:

    DOOR_ROLE_NAME = 'Control de accesos'
    RETENTION_DAYS = 90

    # ── Enlace de la organización ──────────────────────────────────────

    @classmethod
    def invite_expiry(cls, event):
        """00:00 hora de México del día en que arranca el evento."""
        return datetime.datetime.combine(
            event.start_date, datetime.time.min, tzinfo=timezone.get_default_timezone(),
        )

    @classmethod
    @transaction.atomic
    def link_organization(cls, *, event, organization, user):
        event_org, _ = EventOrganization.objects.get_or_create(
            event=event, organization=organization, defaults={'created_by': user},
        )
        return event_org

    @classmethod
    def issue_invite(cls, *, event_org):
        """Genera (o regenera) el enlace. Regenerar anula el anterior."""
        event_org.invite_nonce = staff_tokens.new_nonce()
        event_org.invite_expires_at = cls.invite_expiry(event_org.event)
        event_org.invite_revoked_at = None
        event_org.save(update_fields=['invite_nonce', 'invite_expires_at', 'invite_revoked_at'])
        logger.info('Invite issued: event_org=%s', event_org.pk)
        return cls.invite_token(event_org)

    @classmethod
    def invite_token(cls, event_org):
        if not event_org.invite_nonce:
            return None
        return staff_tokens.make_token(event_org.pk, event_org.invite_nonce, staff_tokens.INVITE_SALT)

    @classmethod
    def revoke_invite(cls, *, event_org):
        event_org.invite_revoked_at = timezone.now()
        event_org.save(update_fields=['invite_revoked_at'])

    @classmethod
    def resolve_invite(cls, token):
        parsed = staff_tokens.parse_token(token, staff_tokens.INVITE_SALT)
        if parsed is None:
            return None
        pk, nonce = parsed
        event_org = (
            EventOrganization.objects.select_related('event', 'organization').filter(pk=pk).first()
        )
        if event_org is None or not event_org.invite_nonce:
            return None
        if not secrets.compare_digest(event_org.invite_nonce, nonce):
            return None
        if event_org.invite_revoked_at is not None:
            return None
        if event_org.invite_expires_at is None or timezone.now() >= event_org.invite_expires_at:
            return None
        if event_org.event.status in _CLOSED_EVENT_STATUSES:
            return None
        return event_org

    # ── Alta y revisión ─────────────────────────────────────────────────

    @classmethod
    @transaction.atomic
    def add_member(cls, *, event_org, data, source, user=None):
        member = StaffMember(event_organization=event_org, source=source)
        for field in _EDITABLE_FIELDS:
            if field in data:
                setattr(member, field, data[field])
        if source == StaffMember.SOURCE_ADMIN:
            # Lo que captura administración no necesita revisión.
            member.status = StaffMember.STATUS_ACCEPTED
            member.badge_nonce = staff_tokens.new_nonce()
            member.reviewed_by = user
            member.reviewed_at = timezone.now()
        member.save()
        return member

    @classmethod
    def _require_pending(cls, member):
        if member.status != StaffMember.STATUS_PENDING:
            raise ValidationError(
                'Solo se corrige lo pendiente: este elemento ya fue revisado por administración.'
            )

    @classmethod
    def _apply_edit(cls, member, data):
        """Copia los campos editables. La foto solo se reemplaza con un archivo
        nuevo (False/None/'' se ignoran) y la anterior se borra al confirmar."""
        old_photo = ''
        if member.pk:
            old_photo = (
                StaffMember.objects.filter(pk=member.pk).values_list('photo', flat=True).first() or ''
            )
        for field in _EDITABLE_FIELDS:
            if field not in data:
                continue
            if field == 'photo' and not data[field]:
                continue
            setattr(member, field, data[field])
        member.save()
        if old_photo and member.photo and member.photo.name != old_photo:
            _delete_file_on_commit(member.photo.storage, old_photo)
        return member

    @classmethod
    @transaction.atomic
    def update_pending_member(cls, *, member, data):
        cls._require_pending(member)
        return cls._apply_edit(member, data)

    @classmethod
    @transaction.atomic
    def admin_update_member(cls, *, member, data, user):
        """El ADMIN corrige a un elemento en cualquier estado; no toca su
        estado ni su gafete."""
        cls._apply_edit(member, data)
        logger.info('Staff member %s edited by admin user=%s', member.pk, getattr(user, 'pk', None))
        return member

    @classmethod
    @transaction.atomic
    def remove_pending_member(cls, *, member):
        cls._require_pending(member)
        if member.photo:
            _delete_file_on_commit(member.photo.storage, member.photo.name)
        member.delete()

    @classmethod
    @transaction.atomic
    def accept(cls, *, member, user):
        if member.status != StaffMember.STATUS_PENDING:
            raise ValidationError('Solo se aceptan elementos pendientes.')
        member.status = StaffMember.STATUS_ACCEPTED
        member.badge_nonce = staff_tokens.new_nonce()
        member.reviewed_by = user
        member.reviewed_at = timezone.now()
        member.save()
        return member

    @classmethod
    @transaction.atomic
    def reject(cls, *, member, user):
        """Rechaza un pendiente o da de baja un aceptado. Anula su gafete."""
        if member.status == StaffMember.STATUS_REJECTED:
            raise ValidationError('El elemento ya está rechazado.')
        member.status = StaffMember.STATUS_REJECTED
        member.badge_nonce = ''
        member.reviewed_by = user
        member.reviewed_at = timezone.now()
        member.save()
        return member

    # ── Gafete y puerta ─────────────────────────────────────────────────

    @classmethod
    def badge_token(cls, member):
        if member.status != StaffMember.STATUS_ACCEPTED or not member.badge_nonce:
            return None
        return staff_tokens.make_token(member.pk, member.badge_nonce, staff_tokens.BADGE_SALT)

    @classmethod
    def resolve_badge(cls, token):
        parsed = staff_tokens.parse_token(token, staff_tokens.BADGE_SALT)
        if parsed is None:
            return None
        pk, nonce = parsed
        member = (
            StaffMember.objects
            .select_related('event_organization__event', 'event_organization__organization', 'role')
            .filter(pk=pk)
            .first()
        )
        if member is None or not member.badge_nonce:
            return None
        if not secrets.compare_digest(member.badge_nonce, nonce):
            return None
        if member.status != StaffMember.STATUS_ACCEPTED:
            return None
        if member.event.status in _CLOSED_EVENT_STATUSES:
            return None
        return member

    @classmethod
    def can_operate_door(cls, user, event):
        if not user.is_authenticated:
            return False
        if user.is_superuser or user.roles.filter(name='ADMIN').exists():
            return True
        return EventStaffAssignment.objects.filter(
            event=event, user=user,
            role__name__iexact=cls.DOOR_ROLE_NAME, role__is_active=True,
        ).exists()

    @classmethod
    def is_inside(cls, member):
        last = member.access_logs.order_by('-recorded_at', '-pk').first()
        return bool(last and last.direction == StaffAccessLog.DIRECTION_IN)

    @classmethod
    @transaction.atomic
    def record_access(cls, *, member, direction, user):
        if not cls.can_operate_door(user, member.event):
            raise PermissionDenied('No tienes permiso para registrar accesos en este evento.')
        # Serializa dos toques simultáneos sobre el mismo elemento.
        member = StaffMember.objects.select_for_update().get(pk=member.pk)
        inside = cls.is_inside(member)
        if direction == StaffAccessLog.DIRECTION_IN and inside:
            raise ValidationError('Este elemento ya está dentro: registra primero su salida.')
        if direction == StaffAccessLog.DIRECTION_OUT and not inside:
            raise ValidationError('Este elemento no está dentro: registra primero su entrada.')
        return StaffAccessLog.objects.create(member=member, direction=direction, recorded_by=user)

    # ── Retención ───────────────────────────────────────────────────────

    @classmethod
    def purge_personal_data(cls, *, today=None):
        """Borra foto y teléfono 90 días después del fin del evento."""
        today = today or timezone.localdate()
        cutoff = today - datetime.timedelta(days=cls.RETENTION_DAYS)
        members = StaffMember.objects.filter(
            event_organization__event__end_date__lte=cutoff,
            personal_data_purged_at__isnull=True,
        )
        count = 0
        for member in members.order_by('pk'):
            try:
                with transaction.atomic():
                    photo_name = member.photo.name if member.photo else ''
                    storage = member.photo.storage
                    member.photo = ''
                    member.phone = ''
                    member.personal_data_purged_at = timezone.now()
                    member.save()
                    _delete_file_on_commit(storage, photo_name)
                count += 1
            except Exception:
                logger.exception('Purge failed for staff member %s', member.pk)
        logger.info('External staff personal data purged: %s members', count)
        return count

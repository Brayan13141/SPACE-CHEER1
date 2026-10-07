"""Ciclo de vida del evento: alta, transiciones de estado y precondiciones."""

import logging

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from events.models import Event, EventResult, EventTeamRegistration

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Allowed status transitions for Event
# ---------------------------------------------------------------------------

_ALLOWED_TRANSITIONS = {
    Event.STATUS_DRAFT: {Event.STATUS_REGISTRATION_OPEN, Event.STATUS_CANCELLED},
    Event.STATUS_REGISTRATION_OPEN: {Event.STATUS_REGISTRATION_CLOSED, Event.STATUS_CANCELLED},
    Event.STATUS_REGISTRATION_CLOSED: {Event.STATUS_IN_PROGRESS, Event.STATUS_CANCELLED},
    Event.STATUS_IN_PROGRESS: {Event.STATUS_COMPLETED, Event.STATUS_CANCELLED},
    Event.STATUS_COMPLETED: set(),
    Event.STATUS_CANCELLED: set(),
}

_TRANSITION_META = {
    Event.STATUS_REGISTRATION_OPEN: {
        'label': 'Abrir Inscripciones',
        'description': 'Permite a los coaches registrar sus equipos al evento.',
        'icon': 'bi-unlock',
        'btn_class': 'success',
        'confirm': False,
    },
    Event.STATUS_REGISTRATION_CLOSED: {
        'label': 'Cerrar Inscripciones',
        'description': 'Congela el registro de equipos. Requiere al menos 2 equipos.',
        'icon': 'bi-lock',
        'btn_class': 'warning',
        'confirm': True,
    },
    Event.STATUS_IN_PROGRESS: {
        'label': 'Iniciar Evento',
        'description': 'Marca el evento como en curso. Los jueces pueden evaluar.',
        'icon': 'bi-play-circle',
        'btn_class': 'primary',
        'confirm': True,
    },
    Event.STATUS_COMPLETED: {
        'label': 'Completar Evento',
        'description': 'Cierra el evento. Requiere resultados calculados.',
        'icon': 'bi-check-circle',
        'btn_class': 'info',
        'confirm': True,
    },
    Event.STATUS_CANCELLED: {
        'label': 'Cancelar Evento',
        'description': 'Cancela el evento permanentemente. Acción irreversible.',
        'icon': 'bi-x-circle',
        'btn_class': 'danger',
        'confirm': True,
    },
}

# Orden lógico de presentación en la UI
_TRANSITION_ORDER = [
    Event.STATUS_REGISTRATION_OPEN,
    Event.STATUS_REGISTRATION_CLOSED,
    Event.STATUS_IN_PROGRESS,
    Event.STATUS_COMPLETED,
    Event.STATUS_CANCELLED,
]


# ---------------------------------------------------------------------------
# EventService
# ---------------------------------------------------------------------------

class EventService:

    @classmethod
    @transaction.atomic
    def create_event(cls, *, name, organizer, event_type, start_date, end_date, **kwargs) -> Event:
        # Build the Event instance from explicit args plus any extra kwargs
        event = Event(
            name=name,
            organizer=organizer,
            event_type=event_type,
            start_date=start_date,
            end_date=end_date,
            **kwargs,
        )
        event.save()
        logger.info('Event created: id=%s name=%r organizer=%s', event.pk, event.name, organizer)
        return event

    @classmethod
    @transaction.atomic
    def transition_status(cls, *, event, new_status, user) -> Event:
        # El organizador, un superusuario o cualquier ADMIN: igual que para
        # aceptar inscripciones, que ya admitía a cualquier ADMIN.
        is_admin = user.roles.filter(name='ADMIN').exists()
        if not (user.is_superuser or is_admin or event.organizer_id == user.pk):
            raise PermissionDenied('Solo un administrador o el organizador pueden cambiar el estado del evento.')

        allowed = _ALLOWED_TRANSITIONS.get(event.status, set())
        if new_status not in allowed:
            raise ValidationError(
                f"Cannot transition event from '{event.status}' to '{new_status}'. "
                f"Allowed targets: {sorted(allowed) or 'none (terminal state)'}."
            )

        # Enforce preconditions — same checks shown in the UI
        blocking = cls._check_transition_preconditions(event, new_status)
        if blocking:
            raise ValidationError(
                'No se puede cambiar el estado: ' + '; '.join(blocking)
            )

        old_status = event.status
        event.status = new_status
        event.save()

        if new_status == Event.STATUS_CANCELLED:
            cls._cancel_open_stays(event=event, user=user)
        logger.info(
            'Event status transitioned: id=%s %s → %s by user=%s',
            event.pk, old_status, new_status, user,
        )
        return event

    @classmethod
    def _cancel_open_stays(cls, *, event, user):
        """Cancela las estancias que no han hecho check-in. Las ya alojadas se
        quedan: alguien está físicamente en el hotel y su salida se registra a
        mano."""
        from hospitality.models import Stay
        from hospitality.services import HospitalityService

        for stay in Stay.objects.filter(
            event=event, status__in=(Stay.REQUESTED, Stay.CONFIRMED),
        ):
            HospitalityService.cancel_stay(stay=stay, cancelled_by=user)

    @classmethod
    def get_registered_teams_count(cls, event) -> int:
        # Count only ACCEPTED registrations for the given event
        return EventTeamRegistration.objects.filter(
            event=event,
            status=EventTeamRegistration.STATUS_ACCEPTED,
        ).count()

    @classmethod
    def is_team_registered(cls, event, team) -> bool:
        # True if any non-WITHDRAWN registration exists for this team/event pair
        return EventTeamRegistration.objects.filter(
            event=event,
            team=team,
        ).exclude(status=EventTeamRegistration.STATUS_WITHDRAWN).exists()

    @classmethod
    def get_transition_readiness(cls, event) -> list:
        """
        Devuelve lista ordenada de dicts para cada transición permitida desde
        el estado actual del evento. Cada dict contiene:
          status, label, icon, btn_class, confirm, ready (bool), blocking (list[str])
        """
        allowed = _ALLOWED_TRANSITIONS.get(event.status, set())
        result = []
        for target in _TRANSITION_ORDER:
            if target not in allowed:
                continue
            meta = _TRANSITION_META.get(target, {})
            blocking = cls._check_transition_preconditions(event, target)
            result.append({
                'status': target,
                'label': meta.get('label', target),
                'description': meta.get('description', ''),
                'icon': meta.get('icon', 'bi-arrow-right'),
                'btn_class': meta.get('btn_class', 'secondary'),
                'confirm': meta.get('confirm', False),
                'ready': not blocking,
                'blocking': blocking,
            })
        return result

    @classmethod
    def _check_transition_preconditions(cls, event, target_status) -> list:
        """Devuelve lista de pasos pendientes que bloquean la transición."""
        blocking = []

        if target_status == Event.STATUS_REGISTRATION_OPEN:
            if not event.categories.exists():
                blocking.append('Agrega al menos una categoría de competencia')
            if not event.judging_criteria.filter(is_active=True).exists():
                blocking.append('Agrega al menos un criterio de evaluación activo')
            if not event.registration_open:
                blocking.append('Define la fecha de apertura de inscripciones')
            if not event.registration_close:
                blocking.append('Define la fecha de cierre de inscripciones')
            if event.start_date and event.start_date < timezone.localdate():
                blocking.append('La fecha de inicio del evento ya pasó')

        elif target_status == Event.STATUS_REGISTRATION_CLOSED:
            # Cada categoría debe tener ≥2 equipos activos (PENDING o ACCEPTED)
            short_categories = []
            for cat in event.categories.all():
                count = EventTeamRegistration.objects.filter(
                    category=cat,
                    status__in=[
                        EventTeamRegistration.STATUS_PENDING,
                        EventTeamRegistration.STATUS_ACCEPTED,
                    ],
                ).count()
                if count < 2:
                    short_categories.append(f'"{cat.name}" ({count}/2)')
            if short_categories:
                blocking.append(
                    'Las siguientes categorías necesitan al menos 2 equipos registrados: '
                    + ', '.join(short_categories)
                )

        elif target_status == Event.STATUS_IN_PROGRESS:
            # Cada categoría debe tener ≥2 equipos ACEPTADOS
            short_categories = []
            for cat in event.categories.all():
                count = EventTeamRegistration.objects.filter(
                    category=cat,
                    status=EventTeamRegistration.STATUS_ACCEPTED,
                ).count()
                if count < 2:
                    short_categories.append(f'"{cat.name}" ({count}/2)')
            if short_categories:
                blocking.append(
                    'Las siguientes categorías necesitan al menos 2 equipos aceptados: '
                    + ', '.join(short_categories)
                )

        elif target_status == Event.STATUS_COMPLETED:
            has_results = EventResult.objects.filter(
                team_registration__event=event,
            ).exists()
            if not has_results:
                blocking.append('Calcula al menos un resultado antes de completar el evento')

        return blocking

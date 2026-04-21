import datetime
import logging
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from .models import (
    Event,
    EventParticipant,
    EventResult,
    EventScore,
    EventTeamRegistration,
)

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
        # Only the event organizer or a superuser may change status
        if not (user.is_superuser or event.organizer_id == user.pk):
            raise PermissionDenied('Only the event organizer or a superuser can change event status.')

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
        logger.info(
            'Event status transitioned: id=%s %s → %s by user=%s',
            event.pk, old_status, new_status, user,
        )
        return event

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
            if event.start_date and event.start_date < datetime.date.today():
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


# ---------------------------------------------------------------------------
# EventRegistrationService
# ---------------------------------------------------------------------------

class EventRegistrationService:

    @classmethod
    @transaction.atomic
    def register_team(
        cls, *, event, team, category, registered_by, notes=''
    ) -> EventTeamRegistration:
        # Registration is only allowed while event.is_registration_open
        if not event.is_registration_open:
            raise ValidationError('Registration is not currently open for this event.')

        # Team must not already have a non-withdrawn registration
        if EventService.is_team_registered(event, team):
            raise ValidationError('This team is already registered for this event.')

        # Category must belong to the event
        if category.event_id != event.pk:
            raise ValidationError('The selected category does not belong to this event.')

        # Un coach solo puede tener un equipo por categoría en el mismo evento
        if EventTeamRegistration.objects.filter(
            event=event,
            category=category,
            team__coach=registered_by,
        ).exclude(status=EventTeamRegistration.STATUS_WITHDRAWN).exists():
            raise ValidationError(
                f'Ya tienes un equipo registrado en la categoría "{category.name}" para este evento.'
            )

        # Enforce global max_teams cap (ACCEPTED count)
        if event.max_teams is not None:
            accepted_count = EventService.get_registered_teams_count(event)
            if accepted_count >= event.max_teams:
                raise ValidationError('Este evento ya alcanzó el límite máximo de equipos aceptados.')

        # Enforce per-category max_teams cap (ACCEPTED count in this category)
        if category.max_teams is not None:
            category_accepted = EventTeamRegistration.objects.filter(
                category=category,
                status=EventTeamRegistration.STATUS_ACCEPTED,
            ).count()
            if category_accepted >= category.max_teams:
                raise ValidationError(
                    f'La categoría "{category.name}" ya alcanzó su límite de '
                    f'{category.max_teams} equipos aceptados.'
                )

        registration = EventTeamRegistration(
            event=event,
            team=team,
            category=category,
            registered_by=registered_by,
            status=EventTeamRegistration.STATUS_PENDING,
            notes=notes,
        )
        registration.save()
        logger.info(
            'Team registered: event=%s team=%s category=%s by=%s',
            event.pk, team.pk, category.pk, registered_by,
        )

        # Auto-create an EventParticipant record for the team coach if one exists
        coach = getattr(team, 'coach', None)
        if coach is not None:
            try:
                EventParticipant.objects.get_or_create(
                    event=event,
                    user=coach,
                    defaults={
                        'role': EventParticipant.ROLE_COACH,
                        'team_registration': registration,
                    },
                )
            except Exception:
                # Coach participant creation is best-effort; log but don't abort
                logger.warning(
                    'Could not create EventParticipant for coach=%s event=%s',
                    coach, event.pk, exc_info=True,
                )

        return registration

    @classmethod
    @transaction.atomic
    def accept_registration(cls, *, registration, user) -> EventTeamRegistration:
        # Superuser, organizer, or any ADMIN role may accept registrations
        is_admin = user.roles.filter(name='ADMIN').exists()
        if not (user.is_superuser or is_admin or registration.event.organizer_id == user.pk):
            raise PermissionDenied('Only an admin or the event organizer can accept registrations.')

        registration.status = EventTeamRegistration.STATUS_ACCEPTED
        registration.save()
        logger.info('Registration accepted: id=%s by user=%s', registration.pk, user)
        return registration

    @classmethod
    @transaction.atomic
    def reject_registration(cls, *, registration, user, notes='') -> EventTeamRegistration:
        # Superuser, organizer, or any ADMIN role may reject registrations
        is_admin = user.roles.filter(name='ADMIN').exists()
        if not (user.is_superuser or is_admin or registration.event.organizer_id == user.pk):
            raise PermissionDenied('Only an admin or the event organizer can reject registrations.')

        registration.status = EventTeamRegistration.STATUS_REJECTED
        if notes:
            registration.notes = notes
        registration.save()
        logger.info('Registration rejected: id=%s by user=%s', registration.pk, user)
        return registration

    @classmethod
    @transaction.atomic
    def withdraw_registration(cls, *, registration, user) -> EventTeamRegistration:
        # Solo se puede retirar si está PENDING o ACCEPTED
        if registration.status not in (
            EventTeamRegistration.STATUS_PENDING,
            EventTeamRegistration.STATUS_ACCEPTED,
        ):
            raise ValidationError(
                f'No se puede cancelar un registro en estado "{registration.get_status_display()}".'
            )

        # Allowed for: the original submitter, the team coach, or a superuser
        team = registration.team
        team_coach = getattr(team, 'coach', None)
        is_registered_by = registration.registered_by_id == user.pk
        is_coach = team_coach is not None and team_coach.pk == user.pk
        if not (user.is_superuser or is_registered_by or is_coach):
            raise PermissionDenied(
                'Only the submitter, the team coach, or a superuser can withdraw this registration.'
            )

        registration.status = EventTeamRegistration.STATUS_WITHDRAWN
        registration.save()
        logger.info('Registration withdrawn: id=%s by user=%s', registration.pk, user)
        return registration

    @classmethod
    @transaction.atomic
    def add_participant(
        cls, *, event, user, role, team_registration=None, notes=''
    ) -> EventParticipant:
        # Raise if user already has any participant record for this event
        if EventParticipant.objects.filter(event=event, user=user).exists():
            raise ValidationError('This user is already a participant in this event.')

        participant = EventParticipant(
            event=event,
            user=user,
            role=role,
            team_registration=team_registration,
            notes=notes,
        )
        participant.save()
        logger.info(
            'EventParticipant added: event=%s user=%s role=%s', event.pk, user, role
        )
        return participant


# ---------------------------------------------------------------------------
# EventScoringService
# ---------------------------------------------------------------------------

class EventScoringService:

    @classmethod
    @transaction.atomic
    def submit_score(
        cls, *, team_registration, criteria, judge, score, round='FINAL', notes=''
    ) -> EventScore:
        event = team_registration.event

        # Validate judge assignment only when staff assignments exist (skip in dev mode)
        if event.staff_assignments.exists():
            is_judge = event.staff_assignments.filter(
                user=judge,
                role__is_judge=True,
            ).exists()
            is_admin = judge.is_superuser or judge.roles.filter(name='ADMIN').exists()
            if not is_judge and not is_admin:
                raise PermissionDenied(
                    'El usuario no tiene una asignación activa de juez para este evento.'
                )

        # Upsert: update existing score or create a new one
        score_obj, created = EventScore.objects.update_or_create(
            team_registration=team_registration,
            criteria=criteria,
            judge=judge,
            round=round,
            defaults={'score': score, 'notes': notes},
        )
        action = 'created' if created else 'updated'
        logger.info(
            'EventScore %s: team_registration=%s criteria=%s judge=%s round=%s score=%s',
            action, team_registration.pk, criteria.pk, judge, round, score,
        )
        return score_obj

    @classmethod
    @transaction.atomic
    def compute_result(cls, *, team_registration, category, round='FINAL') -> EventResult:
        # Fetch all scores for active criteria belonging to this registration/round
        scores = EventScore.objects.filter(
            team_registration=team_registration,
            round=round,
            criteria__is_active=True,
        ).select_related('criteria')

        # Weighted average: sum(score * weight) / sum(weight)
        total_weight = Decimal('0')
        weighted_sum = Decimal('0')
        for s in scores:
            w = s.criteria.weight
            weighted_sum += s.score * w
            total_weight += w

        total_score = (weighted_sum / total_weight) if total_weight else Decimal('0')

        # Upsert EventResult — placement is intentionally left untouched here
        result, created = EventResult.objects.update_or_create(
            team_registration=team_registration,
            category=category,
            round=round,
            defaults={'total_score': total_score},
        )
        action = 'created' if created else 'updated'
        logger.info(
            'EventResult %s: team_registration=%s category=%s round=%s total_score=%s',
            action, team_registration.pk, category.pk, round, total_score,
        )
        return result

    @classmethod
    def get_leaderboard(cls, event, category, round='FINAL') -> list:
        # Return published EventResult objects ordered by total_score descending
        return list(
            EventResult.objects.filter(
                category=category,
                round=round,
                published=True,
                team_registration__event=event,
            ).select_related('team_registration', 'team_registration__team')
            .order_by('-total_score')
        )

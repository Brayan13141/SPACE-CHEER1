"""Inscripción de equipos y participantes."""

import logging

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from events.models import Event, EventParticipant, EventTeamRegistration

from .core import EventService

logger = logging.getLogger(__name__)


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
            coach_role = (
                EventParticipant.ROLE_HEADCOACH
                if coach.is_headcoach
                else EventParticipant.ROLE_COACH
            )
            try:
                EventParticipant.objects.get_or_create(
                    event=event,
                    user=coach,
                    defaults={
                        'role': coach_role,
                        'team_registration': registration,
                    },
                )
            except Exception:
                logger.warning(
                    'Could not create EventParticipant for coach=%s event=%s',
                    coach, event.pk, exc_info=True,
                )

        # Auto-create EventParticipant for every active accepted athlete on the team
        athlete_memberships = team.memberships.filter(
            status='accepted',
            is_active=True,
            role_in_team='ATHLETE',
        ).select_related('user')

        for membership in athlete_memberships:
            try:
                EventParticipant.objects.get_or_create(
                    event=event,
                    user=membership.user,
                    defaults={
                        'role': EventParticipant.ROLE_ATHLETE,
                        'team_registration': registration,
                    },
                )
            except Exception:
                logger.warning(
                    'Could not create EventParticipant for athlete=%s event=%s',
                    membership.user, event.pk, exc_info=True,
                )

        return registration

    @classmethod
    @transaction.atomic
    def accept_registration(cls, *, registration, user) -> EventTeamRegistration:
        # Superuser, organizer, or any ADMIN role may accept registrations
        is_admin = user.roles.filter(name='ADMIN').exists()
        if not (user.is_superuser or is_admin or registration.event.organizer_id == user.pk):
            raise PermissionDenied('Only an admin or the event organizer can accept registrations.')

        # Bloquea el evento para serializar aceptaciones: dos admins aceptando
        # a la vez leerían el mismo conteo y rebasarían el cupo.
        event = Event.objects.select_for_update().get(pk=registration.event_id)
        registration = EventTeamRegistration.objects.select_related('category').get(
            pk=registration.pk,
        )

        if registration.status != EventTeamRegistration.STATUS_PENDING:
            raise ValidationError(
                f'Solo se aceptan inscripciones pendientes; esta está '
                f'"{registration.get_status_display()}".'
            )

        # El cupo se revisaba solo al inscribirse, contra los ya aceptados:
        # con varias pendientes, aceptarlas todas lo rebasaba.
        if event.max_teams is not None:
            if EventService.get_registered_teams_count(event) >= event.max_teams:
                raise ValidationError('Este evento ya alcanzó el límite máximo de equipos aceptados.')

        category = registration.category
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

        # Con el evento en curso o cerrado, retirarse reescribiría un
        # resultado que ya se compitió.
        event = registration.event
        if event.status not in (
            Event.STATUS_DRAFT,
            Event.STATUS_REGISTRATION_OPEN,
            Event.STATUS_REGISTRATION_CLOSED,
        ):
            raise ValidationError(
                f'No se puede retirar la inscripción con el evento '
                f'"{event.get_status_display()}".'
            )

        registration.status = EventTeamRegistration.STATUS_WITHDRAWN
        registration.save()
        # Sus participantes dejan de estar en el evento junto con el equipo.
        for participant in registration.participants.exclude(
            status=EventParticipant.STATUS_CANCELLED,
        ):
            participant.status = EventParticipant.STATUS_CANCELLED
            participant.save()
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

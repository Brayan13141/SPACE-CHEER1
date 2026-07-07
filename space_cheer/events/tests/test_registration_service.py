"""
Tests de EventRegistrationService.register_team — auto-creación de
EventParticipant para el coach del equipo con el rol correcto
(HEADCOACH si el usuario tiene ese rol, COACH en caso contrario).
"""

import datetime

import pytest

from accounts.models import Role, User
from events.models import Event, EventCategory, EventParticipant
from events.services import EventRegistrationService
from teams.models import Team

pytestmark = pytest.mark.django_db


def _make_user(username, role_name):
    role, _ = Role.objects.get_or_create(name=role_name, defaults={'is_coach_type': True})
    user = User.objects.create_user(
        username=username, email=f'{username}@test.com', password='pass123',
        profile_completed=True,
    )
    user.roles.add(role)
    return user


def _make_event(organizer):
    return Event.objects.create(
        name='Evento Registro',
        event_type='COMPETITION',
        status=Event.STATUS_REGISTRATION_OPEN,
        organizer=organizer,
        start_date=datetime.date(2026, 9, 1),
        end_date=datetime.date(2026, 9, 2),
    )


def _register(coach):
    admin = _make_user(f'admin_{coach.username}', 'ADMIN')
    event = _make_event(admin)
    category = EventCategory.objects.create(event=event, name='Senior N3')
    team = Team.objects.create(
        name=f'Equipo {coach.username}', coach=coach, city='León', phone='4771234567',
    )
    registration = EventRegistrationService.register_team(
        event=event, team=team, category=category, registered_by=coach,
    )
    return event, coach, registration


class TestRegisterTeamParticipantRole:
    def test_role_headcoach_existe_en_choices(self):
        assert ('HEADCOACH', 'Head Coach') in [
            (value, str(label)) for value, label in EventParticipant.ROLE_CHOICES
        ]

    def test_headcoach_se_registra_como_headcoach(self):
        headcoach = _make_user('hc_test', 'HEADCOACH')
        event, coach, _ = _register(headcoach)

        participant = EventParticipant.objects.get(event=event, user=coach)
        assert participant.role == EventParticipant.ROLE_HEADCOACH

    def test_coach_normal_se_registra_como_coach(self):
        coach = _make_user('coach_normal', 'COACH')
        event, coach, _ = _register(coach)

        participant = EventParticipant.objects.get(event=event, user=coach)
        assert participant.role == EventParticipant.ROLE_COACH

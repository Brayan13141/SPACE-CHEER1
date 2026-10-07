"""
Integridad del ciclo de un concurso: cálculo de resultados, cupo y estado al
aceptar inscripciones, y puntajes solo con el evento en curso.

Hallazgos de la verificación del 2026-10-04 contra la BD local: ninguno de
estos casos tenía test y los tres pasaban en silencio.
"""

import datetime
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from accounts.models import Role, User
from events.models import (
    Event, EventCategory, EventJudgingCriteria, EventResult, EventTeamRegistration,
)
from events.services import EventRegistrationService, EventScoringService
from teams.models import Team

pytestmark = pytest.mark.django_db

TODAY = datetime.date.today()


def _user(username, role_name):
    role, _ = Role.objects.get_or_create(name=role_name)
    user = User.objects.create_user(
        username=username, email=f'{username}@test.com', password='pass123',
        profile_completed=True,
    )
    user.roles.add(role)
    return user


@pytest.fixture
def admin():
    return _user('admin_integridad', 'ADMIN')


@pytest.fixture
def event(admin):
    return Event.objects.create(
        name='Copa Integridad',
        event_type='COMPETITION',
        status=Event.STATUS_REGISTRATION_OPEN,
        organizer=admin,
        start_date=TODAY + datetime.timedelta(days=20),
        end_date=TODAY + datetime.timedelta(days=21),
    )


@pytest.fixture
def category(event):
    return EventCategory.objects.create(event=event, name='Senior N2')


def _team(name):
    coach = _user(f'hc_{name.lower()}', 'HEADCOACH')
    return Team.objects.create(name=name, coach=coach, city='León', phone='4771234567')


def _register(event, category, name):
    team = _team(name)
    return EventRegistrationService.register_team(
        event=event, team=team, category=category, registered_by=team.coach,
    )


def _set_status(event, status):
    Event.objects.filter(pk=event.pk).update(status=status)
    event.refresh_from_db()


# ---------------------------------------------------------------------------
# 1. compute_result
# ---------------------------------------------------------------------------

class TestComputeResult:
    def _scored(self, event, category, admin, scores):
        criteria = EventJudgingCriteria.objects.create(
            event=event, name='Técnica', weight=1, max_score=Decimal('10'),
        )
        regs = []
        for name, value in scores:
            reg = _register(event, category, name)
            EventRegistrationService.accept_registration(registration=reg, user=admin)
            regs.append(reg)
        _set_status(event, Event.STATUS_IN_PROGRESS)
        for reg, (_, value) in zip(regs, scores):
            EventScoringService.submit_score(
                team_registration=reg, criteria=criteria, judge=admin,
                score=Decimal(value),
            )
        return regs

    def test_calcula_el_resultado_y_le_asigna_lugar(self, event, category, admin):
        alto, bajo = self._scored(event, category, admin, [('Comets', '9'), ('Meteors', '7')])

        EventScoringService.compute_result(team_registration=bajo, category=category)
        EventScoringService.compute_result(team_registration=alto, category=category)

        assert EventResult.objects.get(team_registration=alto).placement == 1
        assert EventResult.objects.get(team_registration=bajo).placement == 2
        assert EventResult.objects.get(team_registration=alto).total_score == Decimal('9')

    def test_empate_comparte_el_lugar(self, event, category, admin):
        a, b, c = self._scored(
            event, category, admin, [('A', '8'), ('B', '8'), ('C', '5')],
        )
        for reg in (a, b, c):
            EventScoringService.compute_result(team_registration=reg, category=category)

        lugares = {
            r.team_registration_id: r.placement
            for r in EventResult.objects.filter(category=category)
        }
        assert lugares == {a.pk: 1, b.pk: 1, c.pk: 3}


# ---------------------------------------------------------------------------
# 2. accept_registration: cupo y estado
# ---------------------------------------------------------------------------

class TestAcceptRegistration:
    def test_no_rebasa_el_cupo_del_evento(self, event, category, admin):
        Event.objects.filter(pk=event.pk).update(max_teams=2)
        event.refresh_from_db()
        regs = [_register(event, category, n) for n in ('A', 'B', 'C')]
        for reg in regs[:2]:
            EventRegistrationService.accept_registration(registration=reg, user=admin)

        with pytest.raises(ValidationError):
            EventRegistrationService.accept_registration(registration=regs[2], user=admin)

        regs[2].refresh_from_db()
        assert regs[2].status == EventTeamRegistration.STATUS_PENDING

    def test_no_rebasa_el_cupo_de_la_categoria(self, event, category, admin):
        EventCategory.objects.filter(pk=category.pk).update(max_teams=1)
        category.refresh_from_db()
        a = _register(event, category, 'A')
        b = _register(event, category, 'B')
        EventRegistrationService.accept_registration(registration=a, user=admin)

        with pytest.raises(ValidationError):
            EventRegistrationService.accept_registration(registration=b, user=admin)

    def test_no_acepta_una_inscripcion_retirada(self, event, category, admin):
        reg = _register(event, category, 'A')
        EventRegistrationService.withdraw_registration(registration=reg, user=reg.team.coach)

        with pytest.raises(ValidationError):
            EventRegistrationService.accept_registration(registration=reg, user=admin)

        reg.refresh_from_db()
        assert reg.status == EventTeamRegistration.STATUS_WITHDRAWN


# ---------------------------------------------------------------------------
# 3. submit_score solo con el evento en curso
# ---------------------------------------------------------------------------

class TestScoreOnlyInProgress:
    @pytest.fixture
    def setup(self, event, category, admin):
        criteria = EventJudgingCriteria.objects.create(
            event=event, name='Técnica', weight=1, max_score=Decimal('10'),
        )
        reg = _register(event, category, 'A')
        EventRegistrationService.accept_registration(registration=reg, user=admin)
        return reg, criteria

    def _score(self, reg, criteria, admin):
        return EventScoringService.submit_score(
            team_registration=reg, criteria=criteria, judge=admin, score=Decimal('7'),
        )

    def test_puntua_con_el_evento_en_curso(self, event, setup, admin):
        _set_status(event, Event.STATUS_IN_PROGRESS)
        assert self._score(*setup, admin).score == Decimal('7')

    @pytest.mark.parametrize('status', [
        Event.STATUS_REGISTRATION_CLOSED,
        Event.STATUS_COMPLETED,
        Event.STATUS_CANCELLED,
    ])
    def test_no_puntua_fuera_de_curso(self, event, setup, admin, status):
        _set_status(event, status)
        with pytest.raises(ValidationError):
            self._score(*setup, admin)

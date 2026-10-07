"""
Reglas de ciclo de vida del concurso halladas en la verificación del
2026-10-04 (bugs 7, 8, 9 y 10 del reporte):

- Una inscripción no se retira con el evento en curso o cerrado, y retirarla
  cancela a sus participantes.
- No se crean estancias en eventos completados o cancelados, y cancelar el
  evento cancela las estancias que no han hecho check-in.
- Cualquier ADMIN cambia el estado del evento, no solo quien lo organizó.
- Las inscripciones se abren y cierran con la fecha de México, no la de UTC.
- No se asignan roles de staff desactivados ni se duplican por mayúsculas.
"""

import datetime
from unittest.mock import patch

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone

from accounts.models import Role, User
from events.models import (
    Event, EventCategory, EventParticipant, EventStaffAssignment, EventStaffRole,
    EventTeamRegistration,
)
from events.services import EventRegistrationService, EventService
from hospitality.models import Stay
from hospitality.services import HospitalityService
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
def organizer():
    return _user('organizador', 'ADMIN')


@pytest.fixture
def event(organizer):
    return Event.objects.create(
        name='Copa Ciclo', event_type='COMPETITION',
        status=Event.STATUS_REGISTRATION_OPEN, organizer=organizer,
        start_date=TODAY + datetime.timedelta(days=20),
        end_date=TODAY + datetime.timedelta(days=21),
    )


@pytest.fixture
def registration(event):
    category = EventCategory.objects.create(event=event, name='Senior')
    coach = _user('hc_ciclo', 'HEADCOACH')
    team = Team.objects.create(name='Comets', coach=coach, city='León', phone='4771234567')
    return EventRegistrationService.register_team(
        event=event, team=team, category=category, registered_by=coach,
    )


def _set_status(event, status):
    Event.objects.filter(pk=event.pk).update(status=status)
    event.refresh_from_db()


# ---------------------------------------------------------------------------
# 7. Retiro de inscripciones
# ---------------------------------------------------------------------------

class TestWithdraw:
    @pytest.mark.parametrize('status', [
        Event.STATUS_IN_PROGRESS, Event.STATUS_COMPLETED, Event.STATUS_CANCELLED,
    ])
    def test_no_se_retira_con_el_evento_en_curso_o_cerrado(self, event, registration, status):
        _set_status(event, status)
        with pytest.raises(ValidationError):
            EventRegistrationService.withdraw_registration(
                registration=registration, user=registration.team.coach,
            )
        registration.refresh_from_db()
        assert registration.status == EventTeamRegistration.STATUS_PENDING

    def test_se_retira_con_inscripciones_cerradas(self, event, registration):
        _set_status(event, Event.STATUS_REGISTRATION_CLOSED)
        reg = EventRegistrationService.withdraw_registration(
            registration=registration, user=registration.team.coach,
        )
        assert reg.status == EventTeamRegistration.STATUS_WITHDRAWN

    def test_retirarse_cancela_a_sus_participantes(self, registration):
        assert EventParticipant.objects.filter(team_registration=registration).exists()

        EventRegistrationService.withdraw_registration(
            registration=registration, user=registration.team.coach,
        )

        vivos = EventParticipant.objects.filter(team_registration=registration).exclude(
            status=EventParticipant.STATUS_CANCELLED,
        )
        assert not vivos.exists()


# ---------------------------------------------------------------------------
# 7. Estancias y estado del evento
# ---------------------------------------------------------------------------

class TestStaysFollowEvent:
    @pytest.mark.parametrize('status', [Event.STATUS_COMPLETED, Event.STATUS_CANCELLED])
    def test_no_se_crean_estancias_en_evento_cerrado(self, event, organizer, status):
        _set_status(event, status)
        guest = _user('huesped', 'ATHLETE')
        with pytest.raises(ValidationError):
            HospitalityService.create_stay(event=event, user=guest, created_by=organizer)

    def test_cancelar_el_evento_cancela_las_estancias_sin_check_in(self, event, organizer):
        _set_status(event, Event.STATUS_DRAFT)
        stay = HospitalityService.create_stay(
            event=event, user=_user('huesped', 'ATHLETE'), created_by=organizer,
        )

        EventService.transition_status(
            event=event, new_status=Event.STATUS_CANCELLED, user=organizer,
        )

        stay.refresh_from_db()
        assert stay.status == Stay.CANCELLED


# ---------------------------------------------------------------------------
# 8. Quién cambia el estado del evento
# ---------------------------------------------------------------------------

class TestWhoTransitions:
    def test_otro_admin_cambia_el_estado(self, event):
        otro_admin = _user('otro_admin', 'ADMIN')
        EventService.transition_status(
            event=event, new_status=Event.STATUS_CANCELLED, user=otro_admin,
        )
        assert event.status == Event.STATUS_CANCELLED

    def test_un_head_coach_no_cambia_el_estado(self, event):
        with pytest.raises(PermissionDenied):
            EventService.transition_status(
                event=event, new_status=Event.STATUS_CANCELLED,
                user=_user('hc_intruso', 'HEADCOACH'),
            )


# ---------------------------------------------------------------------------
# 9. Fecha de México
# ---------------------------------------------------------------------------

class TestLocalDate:
    def test_inscripciones_abiertas_hasta_el_fin_del_dia_en_mexico(self, event):
        # 01:00 UTC del día 5 = 19:00 del día 4 en Ciudad de México.
        utc_now = datetime.datetime(2026, 10, 5, 1, 0, tzinfo=datetime.timezone.utc)
        Event.objects.filter(pk=event.pk).update(
            registration_open=datetime.date(2026, 10, 1),
            registration_close=datetime.date(2026, 10, 4),
        )
        event.refresh_from_db()
        with patch('django.utils.timezone.now', return_value=utc_now):
            assert event.is_registration_open is True


# ---------------------------------------------------------------------------
# 10. Roles de staff
# ---------------------------------------------------------------------------

class TestStaffRoles:
    def test_no_se_asigna_un_rol_desactivado(self, event, organizer):
        inactivo = EventStaffRole.objects.create(name='Rol retirado', is_active=False)
        with pytest.raises(ValidationError):
            EventStaffAssignment.objects.create(
                event=event, user=_user('voluntario', 'STAFF'), role=inactivo,
                assigned_by=organizer,
            )

    def test_no_se_duplica_un_rol_por_mayusculas(self):
        EventStaffRole.objects.create(name='Coordinador de Piso')
        with pytest.raises(ValidationError):
            EventStaffRole.objects.create(name='coordinador de piso')

    def test_desactivar_un_rol_no_rompe_sus_asignaciones_viejas(self, event, organizer):
        rol = EventStaffRole.objects.create(name='Utilero temporal')
        asignacion = EventStaffAssignment.objects.create(
            event=event, user=_user('utilero', 'STAFF'), role=rol, assigned_by=organizer,
        )
        rol.is_active = False
        rol.save()

        asignacion.notes = 'Turno matutino'
        asignacion.save()  # editar una asignación existente sigue permitido

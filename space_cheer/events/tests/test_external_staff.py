"""Staff de concurso sin cuenta: modelos, tokens y servicio.

Spec: docs/superpowers/specs/2026-10-07-event-staff-sin-cuenta-design.md
"""

import datetime

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from accounts.models import Role, User
from events import staff_tokens
from events.models import (
    Event, EventOrganization, EventStaffRole, Organization, StaffAccessLog, StaffMember,
)

pytestmark = pytest.mark.django_db

TODAY = timezone.localdate()


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
    return _user('admin_ext', 'ADMIN')


@pytest.fixture
def event(admin):
    return Event.objects.create(
        name='Copa Externa', event_type='COMPETITION',
        status=Event.STATUS_REGISTRATION_OPEN, organizer=admin,
        start_date=TODAY + datetime.timedelta(days=10),
        end_date=TODAY + datetime.timedelta(days=11),
    )


@pytest.fixture
def role():
    return EventStaffRole.objects.create(name='Cruz Roja')


@pytest.fixture
def event_org(event, admin):
    org = Organization.objects.create(name='Cruz Roja León', kind=Organization.KIND_PUBLIC_INSTITUTION)
    return EventOrganization.objects.create(event=event, organization=org, created_by=admin)


def _member(event_org, role, **kwargs):
    data = dict(full_name='Ana Pérez', phone='4771112233', credential='CR-001', role=role, shift='Sábado 8-14')
    data.update(kwargs)
    return StaffMember.objects.create(event_organization=event_org, **data)


class TestTokens:
    def test_ida_y_vuelta(self):
        token = staff_tokens.make_token(7, 'abc', staff_tokens.BADGE_SALT)
        assert staff_tokens.parse_token(token, staff_tokens.BADGE_SALT) == (7, 'abc')

    def test_otro_salt_no_valida(self):
        token = staff_tokens.make_token(7, 'abc', staff_tokens.BADGE_SALT)
        assert staff_tokens.parse_token(token, staff_tokens.INVITE_SALT) is None

    def test_token_alterado_no_valida(self):
        token = staff_tokens.make_token(7, 'abc', staff_tokens.BADGE_SALT)
        assert staff_tokens.parse_token('8' + token[1:], staff_tokens.BADGE_SALT) is None
        assert staff_tokens.parse_token('basura', staff_tokens.BADGE_SALT) is None


class TestModelos:
    def test_organizacion_no_se_duplica_por_mayusculas(self):
        Organization.objects.create(name='Protección Civil', kind=Organization.KIND_PUBLIC_INSTITUTION)
        with pytest.raises(ValidationError):
            Organization.objects.create(name='protección civil', kind=Organization.KIND_PUBLIC_INSTITUTION)

    def test_una_organizacion_por_evento(self, event_org, admin):
        with pytest.raises(ValidationError):
            EventOrganization.objects.create(
                event=event_org.event, organization=event_org.organization, created_by=admin,
            )

    def test_elemento_nace_pendiente(self, event_org, role):
        member = _member(event_org, role)
        assert member.status == StaffMember.STATUS_PENDING
        assert member.event == event_org.event

    def test_rol_de_juez_no_se_asigna_a_staff_externo(self, event_org):
        juez = EventStaffRole.objects.create(name='Juez X', is_judge=True)
        with pytest.raises(ValidationError):
            _member(event_org, juez)

    def test_rol_desactivado_no_se_asigna(self, event_org):
        inactivo = EventStaffRole.objects.create(name='Taquilla vieja', is_active=False)
        with pytest.raises(ValidationError):
            _member(event_org, inactivo)

    def test_bitacora_es_de_solo_insercion(self, event_org, role, admin):
        member = _member(event_org, role)
        log = StaffAccessLog.objects.create(
            member=member, direction=StaffAccessLog.DIRECTION_IN, recorded_by=admin,
        )
        log.direction = StaffAccessLog.DIRECTION_OUT
        with pytest.raises(ValidationError):
            log.save()
        with pytest.raises(ValidationError):
            log.delete()

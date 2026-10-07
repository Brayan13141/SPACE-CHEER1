"""Staff de concurso sin cuenta: modelos, tokens y servicio.

Spec: docs/superpowers/specs/2026-10-07-event-staff-sin-cuenta-design.md
"""

import datetime
import os
from unittest.mock import patch

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from accounts.models import Role, User
from events import staff_tokens
from events.models import (
    Event, EventOrganization, EventStaffAssignment, EventStaffRole, Organization, StaffAccessLog,
    StaffMember,
)
from events.services import ExternalStaffService as S

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


def _png():
    # PNG 1x1 válido
    return SimpleUploadedFile(
        'f.png',
        b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89'
        b'\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02\xfe\xa7\x35\x81\x84\x00\x00\x00\x00IEND\xaeB`\x82',
        content_type='image/png',
    )


class TestEnlace:
    def test_emitir_y_resolver(self, event_org):
        token = S.issue_invite(event_org=event_org)
        assert S.resolve_invite(token) == event_org

    def test_expira_al_inicio_del_evento(self, event_org):
        token = S.issue_invite(event_org=event_org)
        despues = S.invite_expiry(event_org.event) + datetime.timedelta(minutes=1)
        with patch('events.services.staffing.timezone.now', return_value=despues):
            assert S.resolve_invite(token) is None

    def test_revocado_no_resuelve(self, event_org):
        token = S.issue_invite(event_org=event_org)
        S.revoke_invite(event_org=event_org)
        assert S.resolve_invite(token) is None

    def test_regenerar_anula_el_anterior(self, event_org):
        viejo = S.issue_invite(event_org=event_org)
        nuevo = S.issue_invite(event_org=event_org)
        assert S.resolve_invite(viejo) is None
        assert S.resolve_invite(nuevo) == event_org

    def test_evento_cancelado_no_resuelve(self, event_org):
        token = S.issue_invite(event_org=event_org)
        Event.objects.filter(pk=event_org.event_id).update(status=Event.STATUS_CANCELLED)
        assert S.resolve_invite(token) is None


class TestAltaYRevision:
    def test_por_enlace_nace_pendiente_sin_gafete(self, event_org, role):
        m = S.add_member(event_org=event_org, data={'full_name': 'Luis', 'role': role}, source=StaffMember.SOURCE_LINK)
        assert m.status == StaffMember.STATUS_PENDING
        assert S.badge_token(m) is None

    def test_por_admin_nace_aceptado_con_gafete(self, event_org, role, admin):
        m = S.add_member(event_org=event_org, data={'full_name': 'Luis', 'role': role}, source=StaffMember.SOURCE_ADMIN, user=admin)
        assert m.status == StaffMember.STATUS_ACCEPTED
        assert S.resolve_badge(S.badge_token(m)) == m

    def test_solo_lo_pendiente_se_corrige(self, event_org, role, admin):
        m = S.add_member(event_org=event_org, data={'full_name': 'Luis', 'role': role}, source=StaffMember.SOURCE_LINK)
        S.update_pending_member(member=m, data={'full_name': 'Luis Gómez'})
        S.accept(member=m, user=admin)
        with pytest.raises(ValidationError):
            S.update_pending_member(member=m, data={'full_name': 'Otro'})
        with pytest.raises(ValidationError):
            S.remove_pending_member(member=m)

    def test_rechazar_aceptado_anula_gafete(self, event_org, role, admin):
        m = S.add_member(event_org=event_org, data={'full_name': 'Luis', 'role': role}, source=StaffMember.SOURCE_ADMIN, user=admin)
        token = S.badge_token(m)
        S.reject(member=m, user=admin)
        assert S.resolve_badge(token) is None

    def test_gafete_de_evento_completado_no_sirve(self, event_org, role, admin):
        m = S.add_member(event_org=event_org, data={'full_name': 'Luis', 'role': role}, source=StaffMember.SOURCE_ADMIN, user=admin)
        Event.objects.filter(pk=event_org.event_id).update(status=Event.STATUS_COMPLETED)
        assert S.resolve_badge(S.badge_token(m)) is None


class TestPuerta:
    @pytest.fixture
    def member(self, event_org, role, admin):
        return S.add_member(event_org=event_org, data={'full_name': 'Luis', 'role': role}, source=StaffMember.SOURCE_ADMIN, user=admin)

    @pytest.fixture
    def portero(self, event, admin):
        user = _user('portero', 'STAFF')
        door_role = EventStaffRole.objects.create(name='Control de accesos')
        EventStaffAssignment.objects.create(event=event, user=user, role=door_role, assigned_by=admin)
        return user

    def test_quien_opera_la_puerta(self, event, admin, portero):
        assert S.can_operate_door(admin, event)
        assert S.can_operate_door(portero, event)
        assert not S.can_operate_door(_user('otro_staff', 'STAFF'), event)

    def test_portero_de_otro_evento_no(self, event, admin, portero):
        otro = Event.objects.create(
            name='Otra', event_type='COMPETITION', organizer=admin,
            start_date=TODAY + datetime.timedelta(days=30), end_date=TODAY + datetime.timedelta(days=31),
        )
        assert not S.can_operate_door(portero, otro)

    def test_entrada_y_salida(self, member, portero):
        assert not S.is_inside(member)
        S.record_access(member=member, direction=StaffAccessLog.DIRECTION_IN, user=portero)
        assert S.is_inside(member)
        S.record_access(member=member, direction=StaffAccessLog.DIRECTION_OUT, user=portero)
        assert not S.is_inside(member)

    def test_no_registra_dos_entradas_seguidas(self, member, portero):
        S.record_access(member=member, direction=StaffAccessLog.DIRECTION_IN, user=portero)
        with pytest.raises(ValidationError):
            S.record_access(member=member, direction=StaffAccessLog.DIRECTION_IN, user=portero)
        assert member.access_logs.count() == 1

    def test_sin_permiso_no_registra(self, member):
        with pytest.raises(PermissionDenied):
            S.record_access(member=member, direction=StaffAccessLog.DIRECTION_IN, user=_user('x', 'STAFF'))


class TestPurga:
    def test_borra_foto_y_telefono_a_los_90_dias(
            self, event_org, role, admin, settings, tmp_path, django_capture_on_commit_callbacks):
        settings.MEDIA_ROOT = tmp_path
        m = S.add_member(
            event_org=event_org,
            data={'full_name': 'Luis', 'role': role, 'phone': '4770000000', 'photo': _png()},
            source=StaffMember.SOURCE_ADMIN, user=admin,
        )
        ruta = m.photo.path
        S.record_access(member=m, direction=StaffAccessLog.DIRECTION_IN, user=admin)

        dia_89 = event_org.event.end_date + datetime.timedelta(days=89)
        assert S.purge_personal_data(today=dia_89) == 0

        dia_90 = event_org.event.end_date + datetime.timedelta(days=90)
        with django_capture_on_commit_callbacks(execute=True):
            assert S.purge_personal_data(today=dia_90) == 1
        m.refresh_from_db()
        assert m.phone == '' and not m.photo
        assert m.personal_data_purged_at is not None
        assert m.full_name == 'Luis' and m.access_logs.count() == 1
        assert not os.path.exists(ruta)

        assert S.purge_personal_data(today=dia_90) == 0  # idempotente


class TestTareaDePurga:
    def test_tarea_delega_en_el_servicio(self):
        from events.tasks import purge_external_staff_personal_data
        with patch('events.tasks.ExternalStaffService.purge_personal_data', return_value=3) as purge:
            assert purge_external_staff_personal_data() == 3
        purge.assert_called_once_with()

    def test_esta_agendada_en_beat(self):
        from space_cheer.celery import app
        tareas = {c['task'] for c in app.conf.beat_schedule.values()}
        assert 'events.tasks.purge_external_staff_personal_data' in tareas

# events/tests/test_external_staff_minors.py
"""Minors diferidos de la revision final de 'Staff de concurso sin cuenta'."""

import datetime
from io import BytesIO
from unittest.mock import patch

import pytest
from PIL import Image
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone, translation

from accounts.models import Role, User
from events.models import (
    Event, EventOrganization, EventStaffAssignment, EventStaffRole, Organization,
    StaffAccessLog, StaffMember,
)
from events.services import ExternalStaffService as S
from events.views.external_views import _client_ip

pytestmark = pytest.mark.django_db

TODAY = timezone.localdate()


@pytest.fixture(autouse=True)
def _media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


def _png():
    buf = BytesIO()
    Image.new('RGB', (2, 2), 'white').save(buf, format='PNG')
    return SimpleUploadedFile('f.png', buf.getvalue(), content_type='image/png')


def _user(username, role_name):
    role, _ = Role.objects.get_or_create(name=role_name)
    user = User.objects.create_user(
        username=username, email=f'{username}@test.com', password='pass123', profile_completed=True,
    )
    user.roles.add(role)
    return user


@pytest.fixture
def admin():
    return _user('admin_mn', 'ADMIN')


@pytest.fixture
def event(admin):
    return Event.objects.create(
        name='Copa Minors', event_type='COMPETITION', status=Event.STATUS_REGISTRATION_OPEN,
        organizer=admin, start_date=TODAY + datetime.timedelta(days=10),
        end_date=TODAY + datetime.timedelta(days=11),
    )


@pytest.fixture
def role():
    return EventStaffRole.objects.create(name='Policía')


@pytest.fixture
def event_org(event, admin):
    org = Organization.objects.create(name='Policía Municipal', kind=Organization.KIND_PUBLIC_INSTITUTION)
    return EventOrganization.objects.create(event=event, organization=org, created_by=admin)


@pytest.fixture
def member(event_org, role, admin):
    return S.add_member(
        event_org=event_org, data={'full_name': 'Rosa', 'role': role},
        source=StaffMember.SOURCE_ADMIN, user=admin,
    )


# -- pk con digitos no ASCII ("²" pasa isdigit() y revienta int()) ------

class TestPkSuperindice:
    def test_enlace(self, client, event_org):
        url = reverse('events:staff_invite', args=[S.issue_invite(event_org=event_org)])
        assert client.get(f'{url}?edit=²').status_code == 200
        assert client.post(url, {'action': 'edit', 'member_pk': '²'}).status_code == 404

    def test_admin(self, client, admin, event_org):
        client.force_login(admin)
        url = reverse('events:external_staff', args=[event_org.event.pk])
        assert client.post(url, {'action': 'issue_invite', 'eo_pk': '²'}).status_code == 404
        assert client.post(url, {'action': 'review', 'decision': 'accept', 'member_pks': ['²']}).status_code == 302
        assert client.get(f'{url}?edit_member=²').status_code == 200
        assert client.get(f"{reverse('events:organization_list')}?edit=²").status_code == 200


# -- clave del rate-limit ---------------------------------------------

class TestClaveRateLimit:
    def test_un_x_forwarded_for_falso_no_cambia_la_clave(self, rf):
        # nginx agrega la IP real al final de X-Forwarded-For y fija X-Real-IP;
        # lo que mande el cliente al inicio no debe decidir la clave.
        a = rf.post('/', HTTP_X_FORWARDED_FOR='1.1.1.1, 9.9.9.9', HTTP_X_REAL_IP='9.9.9.9')
        b = rf.post('/', HTTP_X_FORWARDED_FOR='2.2.2.2, 9.9.9.9', HTTP_X_REAL_IP='9.9.9.9')
        assert _client_ip(None, a) == _client_ip(None, b) == '9.9.9.9'

    def test_sin_proxy_usa_remote_addr(self, rf):
        assert _client_ip(None, rf.post('/', REMOTE_ADDR='8.8.8.8')) == '8.8.8.8'


# -- la expiracion sigue a la fecha del evento --------------------------

class TestExpiracion:
    def test_mover_el_evento_recalcula_la_expiracion(self, event_org):
        token = S.issue_invite(event_org=event_org)
        event = event_org.event
        event.start_date = TODAY + datetime.timedelta(days=30)
        event.end_date = TODAY + datetime.timedelta(days=31)
        event.save()
        # Despues de la fecha vieja y antes de la nueva: sigue vivo.
        entre = S.invite_expiry(event) - datetime.timedelta(days=5)
        with patch('events.services.staffing.timezone.now', return_value=entre):
            assert S.resolve_invite(token) is not None
        assert EventOrganization.objects.get(pk=event_org.pk).invite_expires_at == S.invite_expiry(event)

    def test_adelantar_el_evento_lo_vence(self, event_org):
        token = S.issue_invite(event_org=event_org)
        event = event_org.event
        Event.objects.filter(pk=event.pk).update(start_date=TODAY, end_date=TODAY)
        assert S.resolve_invite(token) is None

    def test_no_se_genera_si_el_evento_ya_empezo(self, client, admin, event_org):
        Event.objects.filter(pk=event_org.event_id).update(start_date=TODAY, end_date=TODAY)
        event_org.refresh_from_db()
        with pytest.raises(ValidationError):
            S.issue_invite(event_org=event_org)
        client.force_login(admin)
        url = reverse('events:external_staff', args=[event_org.event_id])
        resp = client.post(url, {'action': 'issue_invite', 'eo_pk': event_org.pk}, follow=True)
        html = resp.content.decode()
        assert 'Enlace generado' not in html
        event_org.refresh_from_db()
        assert not event_org.invite_nonce


# -- organizacion desactivada -----------------------------------------

def test_desactivar_la_organizacion_corta_su_enlace(event_org):
    token = S.issue_invite(event_org=event_org)
    org = event_org.organization
    org.is_active = False
    org.save()
    assert S.resolve_invite(token) is None
    event_org.refresh_from_db()
    assert not event_org.invite_is_active


# -- bitacora: tampoco por queryset -------------------------------------

class TestBitacoraPorQueryset:
    def test_update_bloqueado(self, member, admin):
        S.record_access(member=member, direction=StaffAccessLog.DIRECTION_IN, user=admin)
        with pytest.raises(ValidationError):
            StaffAccessLog.objects.filter(member=member).update(direction=StaffAccessLog.DIRECTION_OUT)
        assert StaffAccessLog.objects.get(member=member).direction == StaffAccessLog.DIRECTION_IN

    def test_delete_bloqueado(self, member, admin):
        S.record_access(member=member, direction=StaffAccessLog.DIRECTION_IN, user=admin)
        with pytest.raises(ValidationError):
            StaffAccessLog.objects.filter(member=member).delete()
        assert StaffAccessLog.objects.filter(member=member).count() == 1


# -- ids unicos en el panel ---------------------------------------------

def test_formularios_de_captura_no_repiten_ids(client, admin, event, event_org):
    otra = Organization.objects.create(name='Cruz Roja', kind=Organization.KIND_PUBLIC_INSTITUTION)
    EventOrganization.objects.create(event=event, organization=otra, created_by=admin)
    client.force_login(admin)
    html = client.get(reverse('events:external_staff', args=[event.pk])).content.decode()
    assert html.count('id="id_full_name"') <= 1
    assert f'id="id_eo{event_org.pk}_full_name"' in html


def test_captura_con_prefijo_de_ids_sigue_guardando(client, admin, event_org, role):
    client.force_login(admin)
    url = reverse('events:external_staff', args=[event_org.event_id])
    client.post(url, {
        'action': 'add_member', 'eo_pk': event_org.pk, 'full_name': 'Luis', 'role': role.pk,
        'phone': '', 'credential': '', 'shift': '', 'photo': _png(),
    })
    assert event_org.members.filter(full_name='Luis', status=StaffMember.STATUS_ACCEPTED).exists()


# -- record_access revisa el estado ya con el candado --------------------

class TestRecordAccessTrasElLock:
    def test_dado_de_baja_entre_lectura_y_registro(self, member, admin):
        viejo = StaffMember.objects.get(pk=member.pk)  # lo que leyo la puerta
        S.reject(member=member, user=admin)
        with pytest.raises(ValidationError):
            S.record_access(member=viejo, direction=StaffAccessLog.DIRECTION_IN, user=admin)
        assert not StaffAccessLog.objects.filter(member=member).exists()

    def test_gafete_reemitido_entre_lectura_y_registro(self, member, admin):
        viejo = StaffMember.objects.get(pk=member.pk)
        S.reject(member=member, user=admin)
        StaffMember.objects.filter(pk=member.pk).update(status=StaffMember.STATUS_PENDING)
        S.accept(member=StaffMember.objects.get(pk=member.pk), user=admin)
        with pytest.raises(ValidationError):
            S.record_access(member=viejo, direction=StaffAccessLog.DIRECTION_IN, user=admin)

    def test_evento_cerrado_entre_lectura_y_registro(self, member, admin):
        viejo = StaffMember.objects.get(pk=member.pk)
        Event.objects.filter(pk=member.event_organization.event_id).update(status=Event.STATUS_COMPLETED)
        with pytest.raises(ValidationError):
            S.record_access(member=viejo, direction=StaffAccessLog.DIRECTION_IN, user=admin)


# -- traducciones ---------------------------------------------------------

class TestTraducciones:
    def test_mensajes_del_servicio_en_ingles(self, member, admin):
        with translation.override('en'):
            with pytest.raises(ValidationError) as exc:
                S.accept(member=member, user=admin)
        assert 'Solo' not in ' '.join(exc.value.messages)

    def test_mensaje_del_enlace_en_ingles(self, client, event_org, role):
        url = reverse('events:staff_invite', args=[S.issue_invite(event_org=event_org)])
        resp = client.post(url, {
            'action': 'add', 'full_name': 'Ana', 'role': role.pk, 'phone': '',
            'credential': '', 'shift': '', 'photo': _png(),
        }, follow=True, HTTP_ACCEPT_LANGUAGE='en')
        html = resp.content.decode()
        assert 'Queda pendiente de revisión' not in html


# -- byte NUL en la ruta de media (preexistente) -------------------------

def test_byte_nul_en_media_da_404(client, admin):
    client.force_login(admin)
    assert client.get('/media/event_staff/a%00b.png').status_code == 404

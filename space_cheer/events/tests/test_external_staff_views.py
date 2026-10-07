# events/tests/test_external_staff_views.py
"""Vistas del staff externo: enlace público, panel admin, gafetes, puerta, hoja."""

import datetime
from io import BytesIO
from unittest.mock import patch

import pytest
from PIL import Image
from django.urls import reverse
from django.utils import timezone

from django.core.files.uploadedfile import SimpleUploadedFile

from accounts.models import PiiAccessLog, Role, User
from events.models import (
    Event, EventOrganization, EventStaffAssignment, EventStaffRole, Organization,
    StaffAccessLog, StaffMember,
)
from events.services import ExternalStaffService as S

pytestmark = pytest.mark.django_db

TODAY = timezone.localdate()


@pytest.fixture(autouse=True)
def _media(settings, tmp_path):
    # TestCase/pytest no limpian MEDIA_ROOT: cada test sube a su propio tmp.
    settings.MEDIA_ROOT = tmp_path


def _png():
    # PNG 1x1 válido, generado con Pillow (pasa magic bytes y verify()).
    buf = BytesIO()
    Image.new('RGB', (1, 1), 'white').save(buf, format='PNG')
    return SimpleUploadedFile('f.png', buf.getvalue(), content_type='image/png')


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
    return _user('admin_v', 'ADMIN')


@pytest.fixture
def event(admin):
    return Event.objects.create(
        name='Copa Vistas', event_type='COMPETITION',
        status=Event.STATUS_REGISTRATION_OPEN, organizer=admin,
        start_date=TODAY + datetime.timedelta(days=10),
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
def invite_url(event_org):
    return reverse('events:staff_invite', args=[S.issue_invite(event_org=event_org)])


def _alta(role, foto=True, **extra):
    data = {'full_name': 'Pedro Ruiz', 'phone': '4779998877', 'credential': 'PM-12',
            'role': role.pk, 'shift': 'Sábado'}
    if foto:
        data['photo'] = _png()
    data.update(extra)
    return data


class TestInvite:
    def test_get_muestra_evento_sin_login(self, client, invite_url, event):
        resp = client.get(invite_url)
        assert resp.status_code == 200
        assert event.name in resp.content.decode()

    def test_token_invalido_muestra_pagina_neutra(self, client, event):
        resp = client.get(reverse('events:staff_invite', args=['basura']))
        assert resp.status_code == 404
        assert event.name not in resp.content.decode()

    def test_alta_entra_pendiente(self, client, invite_url, role, event_org):
        resp = client.post(invite_url, {'action': 'add', **_alta(role)})
        assert resp.status_code == 302
        m = event_org.members.get()
        assert m.status == StaffMember.STATUS_PENDING and m.source == StaffMember.SOURCE_LINK

    def test_invite_vencido_no_crea(self, client, invite_url, role, event_org):
        despues = S.invite_expiry(event_org.event) + datetime.timedelta(minutes=1)
        with patch('events.services.staffing.timezone.now', return_value=despues):
            resp = client.post(invite_url, {'action': 'add', **_alta(role)})
        assert resp.status_code == 404
        assert not event_org.members.exists()

    def test_no_muestra_telefonos_de_vuelta(self, client, invite_url, role, event_org):
        client.post(invite_url, {'action': 'add', **_alta(role)})
        html = client.get(invite_url).content.decode()
        assert 'Pedro Ruiz' in html
        assert '4779998877' not in html

    def test_corrige_y_quita_lo_pendiente(self, client, invite_url, role, event_org):
        client.post(invite_url, {'action': 'add', **_alta(role)})
        m = event_org.members.get()
        # Al corregir no se vuelve a pedir la foto: el elemento ya tiene una.
        client.post(invite_url, {'action': 'edit', 'member_pk': m.pk, **_alta(role, foto=False, full_name='Pedro R.')})
        m.refresh_from_db()
        assert m.full_name == 'Pedro R.'
        client.post(invite_url, {'action': 'remove', 'member_pk': m.pk})
        assert not event_org.members.exists()

    def test_no_corrige_lo_aceptado(self, client, invite_url, role, event_org, admin):
        client.post(invite_url, {'action': 'add', **_alta(role)})
        m = event_org.members.get()
        S.accept(member=m, user=admin)
        client.post(invite_url, {'action': 'edit', 'member_pk': m.pk, **_alta(role, foto=False, full_name='Cambio')})
        m.refresh_from_db()
        assert m.full_name == 'Pedro Ruiz'

    def test_invite_no_toca_elementos_ajenos(self, client, invite_url, role, event, admin):
        otra = Organization.objects.create(name='Cruz Roja', kind=Organization.KIND_PUBLIC_INSTITUTION)
        otra_eo = EventOrganization.objects.create(event=event, organization=otra, created_by=admin)
        ajeno = S.add_member(event_org=otra_eo, data={'full_name': 'Ajeno', 'role': role}, source=StaffMember.SOURCE_LINK)
        resp = client.post(invite_url, {'action': 'remove', 'member_pk': ajeno.pk})
        assert resp.status_code == 404
        assert StaffMember.objects.filter(pk=ajeno.pk).exists()


class TestPanelAdmin:
    def test_solo_admin(self, client, event):
        client.force_login(_user('coach_x', 'HEADCOACH'))
        assert client.get(reverse('events:external_staff', args=[event.pk])).status_code in (302, 403)

    def test_vincular_emitir_y_revocar(self, client, admin, event):
        client.force_login(admin)
        org = Organization.objects.create(name='Limpieza SA', kind=Organization.KIND_VENDOR)
        url = reverse('events:external_staff', args=[event.pk])
        client.post(url, {'action': 'link_org', 'organization': org.pk})
        eo = EventOrganization.objects.get(event=event, organization=org)
        client.post(url, {'action': 'issue_invite', 'eo_pk': eo.pk})
        eo.refresh_from_db()
        assert eo.invite_is_active
        client.post(url, {'action': 'revoke_invite', 'eo_pk': eo.pk})
        eo.refresh_from_db()
        assert not eo.invite_is_active

    def test_aceptar_en_lote(self, client, admin, event_org, role):
        client.force_login(admin)
        a = S.add_member(event_org=event_org, data={'full_name': 'A', 'role': role}, source=StaffMember.SOURCE_LINK)
        b = S.add_member(event_org=event_org, data={'full_name': 'B', 'role': role}, source=StaffMember.SOURCE_LINK)
        client.post(reverse('events:external_staff', args=[event_org.event.pk]),
                    {'action': 'review', 'decision': 'accept', 'member_pks': [a.pk, b.pk]})
        assert set(event_org.members.values_list('status', flat=True)) == {StaffMember.STATUS_ACCEPTED}

    def test_no_revisa_elementos_de_otro_evento(self, client, admin, event_org, role, event):
        otro = Event.objects.create(
            name='Otro', event_type='COMPETITION', organizer=admin,
            start_date=TODAY + datetime.timedelta(days=40), end_date=TODAY + datetime.timedelta(days=41),
        )
        client.force_login(admin)
        m = S.add_member(event_org=event_org, data={'full_name': 'A', 'role': role}, source=StaffMember.SOURCE_LINK)
        client.post(reverse('events:external_staff', args=[otro.pk]),
                    {'action': 'review', 'decision': 'accept', 'member_pks': [m.pk]})
        m.refresh_from_db()
        assert m.status == StaffMember.STATUS_PENDING

    def test_ver_el_panel_se_audita(self, client, admin, event_org, role):
        client.force_login(admin)
        S.add_member(event_org=event_org, data={'full_name': 'A', 'role': role, 'phone': '1'}, source=StaffMember.SOURCE_LINK)
        client.get(reverse('events:external_staff', args=[event_org.event.pk]))
        assert PiiAccessLog.objects.filter(access_type='VIEW_EVENT_STAFF').exists()

    def test_catalogo(self, client, admin):
        client.force_login(admin)
        client.post(reverse('events:organization_list'), {
            'name': 'Protección Civil León', 'kind': Organization.KIND_PUBLIC_INSTITUTION,
        })
        assert Organization.objects.filter(name='Protección Civil León').exists()


class TestGafetesYPuerta:
    @pytest.fixture
    def member(self, event_org, role, admin):
        return S.add_member(event_org=event_org, data={'full_name': 'Rosa', 'role': role, 'photo': _png()},
                            source=StaffMember.SOURCE_ADMIN, user=admin)

    @pytest.fixture
    def portero(self, event, admin):
        user = _user('portero_v', 'STAFF')
        door_role = EventStaffRole.objects.create(name='Control de accesos')
        EventStaffAssignment.objects.create(event=event, user=user, role=door_role, assigned_by=admin)
        return user

    def _door(self, member):
        return reverse('events:staff_door', args=[S.badge_token(member)])

    def test_gafetes_llevan_qr_con_url_de_puerta(self, client, admin, member, event):
        client.force_login(admin)
        html = client.get(reverse('events:external_staff_badges', args=[event.pk])).content.decode()
        assert 'Rosa' in html and '<svg' in html

    def test_puerta_exige_login(self, client, member):
        assert client.get(self._door(member)).status_code == 302

    def test_portero_registra_entrada(self, client, portero, member):
        client.force_login(portero)
        url = self._door(member)
        assert client.get(url).status_code == 200
        client.post(url, {'direction': StaffAccessLog.DIRECTION_IN})
        assert S.is_inside(member)
        assert PiiAccessLog.objects.filter(access_type='VIEW_EVENT_STAFF').exists()

    def test_staff_sin_rol_de_puerta_recibe_403(self, client, member):
        client.force_login(_user('miron', 'STAFF'))
        assert client.get(self._door(member)).status_code == 403

    def test_gafete_anulado_muestra_invalido(self, client, admin, member):
        url = self._door(member)
        S.reject(member=member, user=admin)
        client.force_login(admin)
        resp = client.get(url)
        assert resp.status_code == 404
        assert 'Rosa' not in resp.content.decode()

    def test_foto_de_staff_no_la_ve_otro_usuario(self, client, member, portero):
        url = member.photo.url
        client.force_login(_user('curioso', 'ATHLETE'))
        assert client.get(url).status_code == 404
        client.force_login(portero)
        assert client.get(url).status_code == 200


class TestHojaYBitacora:
    def test_hoja_sin_telefono_y_solo_aceptados(self, client, admin, event_org, role, event):
        S.add_member(event_org=event_org, data={'full_name': 'Visible', 'role': role, 'phone': '4771231234', 'shift': 'Sábado'},
                     source=StaffMember.SOURCE_ADMIN, user=admin)
        S.add_member(event_org=event_org, data={'full_name': 'Pendiente', 'role': role}, source=StaffMember.SOURCE_LINK)
        client.force_login(admin)
        html = client.get(reverse('events:external_staff_sheet', args=[event.pk])).content.decode()
        assert 'Visible' in html
        assert 'Pendiente' not in html
        assert '4771231234' not in html
        assert 'Entrada' in html and 'Salida' in html

    def test_bitacora_lista_accesos(self, client, admin, event_org, role, event):
        m = S.add_member(event_org=event_org, data={'full_name': 'Rosa', 'role': role}, source=StaffMember.SOURCE_ADMIN, user=admin)
        S.record_access(member=m, direction=StaffAccessLog.DIRECTION_IN, user=admin)
        client.force_login(admin)
        html = client.get(reverse('events:external_staff_log', args=[event.pk])).content.decode()
        assert 'Rosa' in html

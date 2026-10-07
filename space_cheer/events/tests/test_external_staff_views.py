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

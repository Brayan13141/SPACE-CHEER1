# events/tests/test_external_staff_fixes.py
"""Regresiones de la revision final de 'Staff de concurso sin cuenta'."""

import datetime
import os
import zoneinfo
from io import BytesIO
from unittest.mock import patch

import pytest
from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from accounts.models import PiiAccessLog, Role, User
from events.models import (
    Event, EventOrganization, EventStaffAssignment, EventStaffRole, Organization, StaffMember,
)
from events.services import ExternalStaffService as S

pytestmark = pytest.mark.django_db

TODAY = timezone.localdate()


@pytest.fixture(autouse=True)
def _media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


def _png(name='f.png', color='white'):
    buf = BytesIO()
    Image.new('RGB', (2, 2), color).save(buf, format='PNG')
    return SimpleUploadedFile(name, buf.getvalue(), content_type='image/png')


def _user(username, role_name):
    role, _ = Role.objects.get_or_create(name=role_name)
    user = User.objects.create_user(
        username=username, email=f'{username}@test.com', password='pass123', profile_completed=True,
    )
    user.roles.add(role)
    return user


@pytest.fixture
def admin():
    return _user('admin_fx', 'ADMIN')


@pytest.fixture
def event(admin):
    return Event.objects.create(
        name='Copa Fixes', event_type='COMPETITION', status=Event.STATUS_REGISTRATION_OPEN,
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
def invite_url(event_org):
    return reverse('events:staff_invite', args=[S.issue_invite(event_org=event_org)])


@pytest.fixture
def link_member(event_org, role):
    return S.add_member(
        event_org=event_org, source=StaffMember.SOURCE_LINK,
        data={'full_name': 'Pedro Ruiz', 'phone': '4779998877', 'role': role,
              'credential': 'PM-12', 'photo': _png('image.png')},
    )


def _data(role, **extra):
    data = {'full_name': 'Pedro Ruiz', 'phone': '4779998877', 'credential': 'PM-12',
            'role': role.pk, 'shift': ''}
    data.update(extra)
    return data


# -- C1 ----------------------------------------------------------------

class TestMediaDotSegments:
    def test_punto_en_la_ruta_no_esquiva_la_autorizacion(self, client, settings, link_member):
        name = os.path.basename(link_member.photo.name)
        client.force_login(_user('curioso', 'ATLETA'))
        assert client.get(f'{settings.MEDIA_URL}./event_staff/photos/{name}').status_code == 404

    def test_designs_punto_punto_no_esquiva_la_autorizacion(self, client, settings, link_member):
        name = os.path.basename(link_member.photo.name)
        client.force_login(_user('curioso2', 'ATLETA'))
        url = f'{settings.MEDIA_URL}designs/../event_staff/photos/{name}'
        assert client.get(url).status_code == 404

    def test_el_portero_si_la_ve_por_la_ruta_canonica(self, client, event, admin, link_member):
        portero = _user('portero_fx', 'STAFF')
        door = EventStaffRole.objects.create(name='Control de accesos')
        EventStaffAssignment.objects.create(event=event, user=portero, role=door, assigned_by=admin)
        client.force_login(portero)
        assert client.get(link_member.photo.url).status_code == 200


# -- I1 ----------------------------------------------------------------

class TestEnlaceNoHaceEco:
    def test_editar_no_devuelve_telefono_ni_ruta_de_foto(self, client, invite_url, link_member):
        html = client.get(f'{invite_url}?edit={link_member.pk}').content.decode()
        assert 'Pedro Ruiz' in html
        assert '4779998877' not in html
        assert 'event_staff/photos' not in html

    def test_telefono_en_blanco_conserva_el_guardado(self, client, invite_url, link_member, role):
        client.post(invite_url, {'action': 'edit', 'member_pk': link_member.pk,
                                 **_data(role, phone='', full_name='Pedro R.')})
        link_member.refresh_from_db()
        assert link_member.full_name == 'Pedro R.' and link_member.phone == '4779998877'

    def test_telefono_nuevo_lo_reemplaza(self, client, invite_url, link_member, role):
        client.post(invite_url, {'action': 'edit', 'member_pk': link_member.pk,
                                 **_data(role, phone='4771112222')})
        link_member.refresh_from_db()
        assert link_member.phone == '4771112222'


# -- I2 ----------------------------------------------------------------

class TestFotoAlCorregir:
    def test_reemplazar_borra_la_foto_anterior(self, link_member, role, django_capture_on_commit_callbacks):
        vieja = link_member.photo.path
        assert os.path.exists(vieja)
        with django_capture_on_commit_callbacks(execute=True):
            S.update_pending_member(member=link_member, data={'photo': _png('nueva.png', 'black')})
        link_member.refresh_from_db()
        assert os.path.exists(link_member.photo.path)
        assert link_member.photo.path != vieja
        assert not os.path.exists(vieja)

    def test_reemplazar_por_el_enlace_borra_la_anterior(
            self, client, invite_url, link_member, role, django_capture_on_commit_callbacks):
        vieja = link_member.photo.path
        with django_capture_on_commit_callbacks(execute=True):
            resp = client.post(invite_url, {'action': 'edit', 'member_pk': link_member.pk,
                                            **_data(role), 'photo': _png('otra.png', 'red')})
        assert resp.status_code == 302
        assert not os.path.exists(vieja)

    def test_bandera_de_limpiar_no_da_500_ni_borra(self, client, invite_url, link_member, role):
        resp = client.post(invite_url, {'action': 'edit', 'member_pk': link_member.pk,
                                        **_data(role), 'photo-clear': 'on'})
        assert resp.status_code == 302
        link_member.refresh_from_db()
        assert link_member.photo

    def test_el_servicio_ignora_false(self, link_member):
        S.update_pending_member(member=link_member, data={'photo': False, 'full_name': 'X'})
        link_member.refresh_from_db()
        assert link_member.photo and link_member.full_name == 'X'

    def test_admin_con_bandera_de_limpiar_no_da_500(self, client, admin, event_org, link_member, role):
        client.force_login(admin)
        url = reverse('events:external_staff', args=[event_org.event.pk])
        resp = client.post(url, {'action': 'edit_member', 'member_pk': link_member.pk,
                                 **_data(role), 'photo-clear': 'on'})
        assert resp.status_code in (200, 302)
        link_member.refresh_from_db()
        assert link_member.photo


# -- I3 ----------------------------------------------------------------

class TestAdminCatalogo:
    def test_edita_una_organizacion(self, client, admin):
        client.force_login(admin)
        org = Organization.objects.create(name='Cruz Rojaa', kind=Organization.KIND_PUBLIC_INSTITUTION)
        url = reverse('events:organization_list')
        html = client.get(f'{url}?edit={org.pk}').content.decode()
        assert 'Cruz Rojaa' in html
        resp = client.post(url, {'action': 'edit_org', 'org_pk': org.pk, 'name': 'Cruz Roja',
                                 'kind': Organization.KIND_PUBLIC_INSTITUTION,
                                 'contact_name': 'Ana', 'contact_phone': '1'})
        assert resp.status_code == 302
        org.refresh_from_db()
        assert org.name == 'Cruz Roja' and org.contact_name == 'Ana'
        assert Organization.objects.count() == 1


class TestAdminPanel:
    def _url(self, event_org):
        return reverse('events:external_staff', args=[event_org.event.pk])

    def test_filtro_por_estado(self, client, admin, event_org, role):
        client.force_login(admin)
        S.add_member(event_org=event_org, data={'full_name': 'Pablo Pend', 'role': role}, source=StaffMember.SOURCE_LINK)
        S.add_member(event_org=event_org, data={'full_name': 'Zoe Ok', 'role': role},
                     source=StaffMember.SOURCE_ADMIN, user=admin)
        html = client.get(self._url(event_org) + '?status=PENDING').content.decode()
        assert 'Pablo Pend' in html and 'Zoe Ok' not in html
        html = client.get(self._url(event_org) + '?status=ACCEPTED').content.decode()
        assert 'Zoe Ok' in html and 'Pablo Pend' not in html
        html = client.get(self._url(event_org)).content.decode()
        assert 'Pablo Pend' in html and 'Zoe Ok' in html
        assert '?status=REJECTED' in html

    def test_admin_edita_un_aceptado_y_la_vista_se_audita(self, client, admin, event_org, role):
        client.force_login(admin)
        m = S.add_member(event_org=event_org, data={'full_name': 'Eror', 'phone': '4770001111', 'role': role,
                                                    'photo': _png()},
                         source=StaffMember.SOURCE_ADMIN, user=admin)
        nonce = m.badge_nonce
        PiiAccessLog.objects.all().delete()
        html = client.get(f'{self._url(event_org)}?edit_member={m.pk}').content.decode()
        assert 'Eror' in html and '4770001111' in html
        assert PiiAccessLog.objects.filter(access_type='VIEW_EVENT_STAFF').exists()
        resp = client.post(self._url(event_org), {'action': 'edit_member', 'member_pk': m.pk,
                                                  **_data(role, full_name='Error', phone='4770002222')})
        assert resp.status_code == 302
        m.refresh_from_db()
        assert m.full_name == 'Error' and m.phone == '4770002222'
        assert m.status == StaffMember.STATUS_ACCEPTED and m.badge_nonce == nonce

    def test_admin_no_edita_elementos_de_otro_evento(self, client, admin, event_org, role):
        otro = Event.objects.create(
            name='Otro', event_type='COMPETITION', organizer=admin,
            start_date=TODAY + datetime.timedelta(days=40), end_date=TODAY + datetime.timedelta(days=41),
        )
        m = S.add_member(event_org=event_org, data={'full_name': 'A', 'role': role}, source=StaffMember.SOURCE_LINK)
        client.force_login(admin)
        client.post(reverse('events:external_staff', args=[otro.pk]),
                    {'action': 'edit_member', 'member_pk': m.pk, **_data(role, full_name='Hack')})
        m.refresh_from_db()
        assert m.full_name == 'A'

    def test_servicio_admin_update_member_no_exige_pendiente(self, admin, event_org, role):
        m = S.add_member(event_org=event_org, data={'full_name': 'A', 'role': role},
                         source=StaffMember.SOURCE_ADMIN, user=admin)
        S.admin_update_member(member=m, data={'full_name': 'B'}, user=admin)
        m.refresh_from_db()
        assert m.full_name == 'B' and m.status == StaffMember.STATUS_ACCEPTED

    def test_captura_invalida_vuelve_a_pintar_con_errores(self, client, admin, event_org, role):
        client.force_login(admin)
        resp = client.post(self._url(event_org), {'action': 'add_member', 'eo_pk': event_org.pk,
                                                  **_data(role, full_name='')})
        assert resp.status_code == 200
        html = resp.content.decode()
        assert 'errorlist' in html or 'invalid-feedback' in html or 'is-invalid' in html
        assert '4779998877' in html  # conserva lo capturado
        assert not event_org.members.exists()


# -- Minor 1 -----------------------------------------------------------

class TestPksNoNumericos:
    def test_enlace(self, client, invite_url):
        assert client.get(f'{invite_url}?edit=abc').status_code == 200
        assert client.post(invite_url, {'action': 'edit', 'member_pk': 'abc'}).status_code == 404
        assert client.post(invite_url, {'action': 'remove', 'member_pk': 'abc'}).status_code == 404

    def test_admin(self, client, admin, event_org):
        client.force_login(admin)
        url = reverse('events:external_staff', args=[event_org.event.pk])
        assert client.post(url, {'action': 'issue_invite', 'eo_pk': 'abc'}).status_code == 404
        assert client.post(url, {'action': 'review', 'decision': 'accept', 'member_pks': ['abc']}).status_code == 302
        assert client.get(f'{url}?edit_member=abc').status_code == 200
        org_url = reverse('events:organization_list')
        assert client.post(org_url, {'action': 'toggle', 'org_pk': 'abc'}).status_code == 404
        assert client.get(f'{org_url}?edit=abc').status_code == 200


# -- Minor 3a ----------------------------------------------------------

def test_invite_expiry_no_depende_de_la_zona_activa(event):
    esperado = S.invite_expiry(event)
    timezone.activate(zoneinfo.ZoneInfo('Asia/Tokyo'))
    try:
        assert S.invite_expiry(event) == esperado
        assert S.invite_expiry(event).tzinfo == timezone.get_default_timezone()
    finally:
        timezone.deactivate()


# -- Minor 4 -----------------------------------------------------------

class TestPurgaAislada:
    def _mk(self, event_org, role, admin, name):
        return S.add_member(event_org=event_org, source=StaffMember.SOURCE_ADMIN, user=admin,
                            data={'full_name': name, 'role': role, 'phone': '1', 'photo': _png(f'{name}.png')})

    def test_un_fallo_no_bloquea_a_los_demas(self, event_org, role, admin, django_capture_on_commit_callbacks):
        malo = self._mk(event_org, role, admin, 'Malo')
        bueno = self._mk(event_org, role, admin, 'Bueno')
        ruta_malo, ruta_bueno = malo.photo.path, bueno.photo.path
        real_save = StaffMember.save

        def save(self, *a, **kw):
            if self.pk == malo.pk:
                raise RuntimeError('boom')
            return real_save(self, *a, **kw)

        dia = event_org.event.end_date + datetime.timedelta(days=90)
        with patch.object(StaffMember, 'save', save), django_capture_on_commit_callbacks(execute=True):
            assert S.purge_personal_data(today=dia) == 1
        bueno.refresh_from_db()
        malo.refresh_from_db()
        assert bueno.personal_data_purged_at is not None and not os.path.exists(ruta_bueno)
        assert malo.personal_data_purged_at is None and os.path.exists(ruta_malo)

    def test_quitar_pendiente_borra_el_archivo_al_confirmar(
            self, link_member, django_capture_on_commit_callbacks):
        ruta = link_member.photo.path
        with django_capture_on_commit_callbacks(execute=False) as callbacks:
            S.remove_pending_member(member=link_member)
        assert os.path.exists(ruta)  # aun no hay commit
        for cb in callbacks:
            cb()
        assert not os.path.exists(ruta)

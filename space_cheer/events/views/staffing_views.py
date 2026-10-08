# events/views/staffing_views.py
"""ADMIN: catálogo de organizaciones y staff externo de cada evento."""

import logging
from itertools import groupby

import segno
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _

from accounts.decorators import role_required
from accounts.services.pii_audit_service import PiiAuditService
from events.forms_staffing import LinkOrganizationForm, OrganizationForm, StaffMemberForm
from events.models import Event, EventOrganization, Organization, StaffAccessLog, StaffMember
from events.services import ExternalStaffService

logger = logging.getLogger(__name__)


def is_pk(value):
    """True si el valor es un pk entero. isdigit() solo tambien acepta "²" y
    digitos de otros alfabetos, que el ORM rechaza con un 500."""
    value = str(value or '')
    return value.isascii() and value.isdigit()


def _pk(value):
    """pk entero o 404: un valor no numerico nunca debe llegar a un 500."""
    if not is_pk(value):
        raise Http404
    return int(value)


@role_required('ADMIN')
def organization_list(request):
    editing = None
    edit_pk = request.GET.get('edit', '')
    if is_pk(edit_pk):
        editing = Organization.objects.filter(pk=edit_pk).first()
    form = OrganizationForm(instance=editing)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'toggle':
            org = get_object_or_404(Organization, pk=_pk(request.POST.get('org_pk')))
            org.is_active = not org.is_active
            org.save()
            return redirect('events:organization_list')
        if action == 'edit_org':
            editing = get_object_or_404(Organization, pk=_pk(request.POST.get('org_pk')))
            form = OrganizationForm(request.POST, instance=editing)
            if form.is_valid():
                form.save()
                messages.success(request, _('Organización actualizada.'))
                return redirect('events:organization_list')
        else:
            editing = None
            form = OrganizationForm(request.POST)
            if form.is_valid():
                form.save()
                messages.success(request, _('Organización agregada.'))
                return redirect('events:organization_list')
    return render(request, 'events/staffing/organizations.html', {
        'organizations': Organization.objects.order_by('name'),
        'form': form,
        'editing': editing,
    })


# Cada tarjeta trae su propio formulario de captura: sin ids propios, los
# <label for> de una tarjeta apuntarían a los campos de la primera.
_EDIT_IDS = 'id_edit_%s'


def _capture_ids(event_org):
    return f'id_eo{event_org.pk}_%s'


def _event_org(event, pk):
    return get_object_or_404(EventOrganization, pk=_pk(pk), event=event)


@role_required('ADMIN')
def external_staff(request, pk):
    event = get_object_or_404(Event, pk=pk)
    link_form = LinkOrganizationForm(event=event)
    bound_form, bound_eo_pk = None, None
    editing, edit_form = None, None

    status_filter = request.GET.get('status', '')
    if status_filter not in {value for value, _label in StaffMember.STATUS_CHOICES}:
        status_filter = ''

    edit_pk = request.GET.get('edit_member', '')
    if request.method == 'GET' and is_pk(edit_pk):
        editing = StaffMember.objects.filter(pk=edit_pk, event_organization__event=event).first()
        if editing is not None:
            edit_form = StaffMemberForm(instance=editing, auto_id=_EDIT_IDS)
            PiiAuditService.log(
                request=request, target_user=None, access_type='VIEW_EVENT_STAFF',
                field_accessed='phone,photo', notes=f'external_staff edit member pk={editing.pk}',
            )

    if request.method == 'POST':
        action = request.POST.get('action')
        stay = False  # True = volver a pintar el panel con errores en vez de redirigir
        try:
            if action == 'link_org':
                link_form = LinkOrganizationForm(request.POST, event=event)
                if link_form.is_valid():
                    ExternalStaffService.link_organization(
                        event=event, organization=link_form.cleaned_data['organization'], user=request.user,
                    )
                    messages.success(request, _('Organización agregada al evento.'))
            elif action == 'issue_invite':
                ExternalStaffService.issue_invite(event_org=_event_org(event, request.POST.get('eo_pk')))
                messages.success(request, _('Enlace generado. Si había uno anterior, ya no sirve.'))
            elif action == 'revoke_invite':
                ExternalStaffService.revoke_invite(event_org=_event_org(event, request.POST.get('eo_pk')))
                messages.success(request, _('Enlace revocado.'))
            elif action == 'add_member':
                event_org = _event_org(event, request.POST.get('eo_pk'))
                member_form = StaffMemberForm(request.POST, request.FILES, auto_id=_capture_ids(event_org))
                if member_form.is_valid():
                    ExternalStaffService.add_member(
                        event_org=event_org, data=member_form.cleaned_data,
                        source=StaffMember.SOURCE_ADMIN, user=request.user,
                    )
                    messages.success(request, _('Elemento capturado y aceptado.'))
                else:
                    messages.error(request, _('Revisa los datos del elemento.'))
                    bound_form, bound_eo_pk = member_form, event_org.pk
                    stay = True
            elif action == 'edit_member':
                editing = get_object_or_404(
                    StaffMember, pk=_pk(request.POST.get('member_pk')), event_organization__event=event,
                )
                edit_form = StaffMemberForm(request.POST, request.FILES, instance=editing, auto_id=_EDIT_IDS)
                if edit_form.is_valid():
                    ExternalStaffService.admin_update_member(
                        member=editing, data=edit_form.cleaned_data, user=request.user,
                    )
                    messages.success(request, _('Elemento actualizado.'))
                else:
                    messages.error(request, _('Revisa los datos del elemento.'))
                    stay = True
            elif action == 'review':
                decision = request.POST.get('decision')
                member_pks = [int(v) for v in request.POST.getlist('member_pks') if is_pk(v)]
                members = StaffMember.objects.filter(pk__in=member_pks, event_organization__event=event)
                done = 0
                for member in members:
                    try:
                        if decision == 'accept':
                            ExternalStaffService.accept(member=member, user=request.user)
                        elif decision == 'reject':
                            ExternalStaffService.reject(member=member, user=request.user)
                        done += 1
                    except ValidationError as e:
                        messages.warning(request, f'{member.full_name}: {" ".join(e.messages)}')
                messages.success(request, _('%(n)s elemento(s) actualizados.') % {'n': done})
        except ValidationError as e:
            messages.error(request, ' '.join(e.messages))
        if not stay:
            return redirect('events:external_staff', pk=pk)

    event_orgs = (
        EventOrganization.objects.filter(event=event)
        .select_related('event', 'organization')
        .prefetch_related('members__role')
    )
    rows = []
    for eo in event_orgs:
        token = ExternalStaffService.invite_token(eo) if eo.invite_is_active else None
        members = list(eo.members.all())
        if status_filter:
            members = [m for m in members if m.status == status_filter]
        rows.append({
            'eo': eo,
            'invite_url': request.build_absolute_uri(reverse('events:staff_invite', args=[token])) if token else None,
            'members': members,
            'form': bound_form if eo.pk == bound_eo_pk else StaffMemberForm(auto_id=_capture_ids(eo)),
            'form_open': eo.pk == bound_eo_pk,
        })

    if any(row['members'] for row in rows):
        # El panel muestra teléfonos y fotos de personas sin cuenta.
        PiiAuditService.log(
            request=request, target_user=None, access_type='VIEW_EVENT_STAFF',
            field_accessed='phone,photo', notes=f'external_staff event pk={event.pk}',
        )

    return render(request, 'events/staffing/event_staff.html', {
        'event': event,
        'rows': rows,
        'link_form': link_form,
        'editing': editing,
        'edit_form': edit_form,
        'status_filter': status_filter,
        'status_choices': StaffMember.STATUS_CHOICES,
    })


@role_required('ADMIN')
def badges(request, pk):
    event = get_object_or_404(Event, pk=pk)
    members = (
        StaffMember.objects.filter(event_organization__event=event, status=StaffMember.STATUS_ACCEPTED)
        .select_related('event_organization__organization', 'role')
        .order_by('event_organization__organization__name', 'full_name')
    )
    cards = []
    for m in members:
        url = request.build_absolute_uri(
            reverse('events:staff_door', args=[ExternalStaffService.badge_token(m)])
        )
        # svg_inline genera solo el <svg> del QR a partir de nuestra propia URL.
        cards.append({'member': m, 'qr': mark_safe(segno.make(url, error='m').svg_inline(scale=3))})
    if cards:
        PiiAuditService.log(
            request=request, target_user=None, access_type='VIEW_EVENT_STAFF',
            field_accessed='photo', notes=f'external_staff badges event pk={event.pk}',
        )
    return render(request, 'events/staffing/badges.html', {'event': event, 'cards': cards})


@role_required('ADMIN')
def sheet(request, pk):
    event = get_object_or_404(Event, pk=pk)
    members = list(
        StaffMember.objects.filter(event_organization__event=event, status=StaffMember.STATUS_ACCEPTED)
        .select_related('event_organization__organization', 'role')
        .order_by('event_organization__organization__name', 'shift', 'full_name')
    )
    groups = []
    for org_name, org_members in groupby(members, key=lambda m: m.event_organization.organization.name):
        org_members = list(org_members)
        shifts = [
            {'shift': shift or '—', 'members': list(items)}
            for shift, items in groupby(org_members, key=lambda m: m.shift)
        ]
        groups.append({'organization': org_name, 'shifts': shifts, 'total': len(org_members)})

    by_role = {}
    for m in members:
        by_role[m.role.name] = by_role.get(m.role.name, 0) + 1

    return render(request, 'events/staffing/sheet.html', {
        'event': event, 'groups': groups, 'by_role': sorted(by_role.items()), 'total': len(members),
    })


@role_required('ADMIN')
def access_log(request, pk):
    event = get_object_or_404(Event, pk=pk)
    logs = (
        StaffAccessLog.objects.filter(member__event_organization__event=event)
        .select_related('member__event_organization__organization', 'member__role', 'recorded_by')
    )
    return render(request, 'events/staffing/access_log.html', {'event': event, 'logs': logs})

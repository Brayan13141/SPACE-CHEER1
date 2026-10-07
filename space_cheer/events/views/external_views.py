# events/views/external_views.py
"""Lo que se abre sin cuenta (el enlace de la organización) y la página de
puerta a la que lleva el QR del gafete."""

import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django_ratelimit.decorators import ratelimit

from accounts.services.pii_audit_service import PiiAuditService
from events.forms_staffing import StaffMemberForm
from events.models import StaffMember
from events.services import ExternalStaffService

logger = logging.getLogger(__name__)


def _client_ip(group, request):
    # Detrás del socket de nginx REMOTE_ADDR llega vacío: se lee X-Forwarded-For.
    return PiiAuditService._get_client_ip(request) or 'unknown'


@ratelimit(key=_client_ip, rate='30/m', method='POST', block=True)
def staff_invite(request, token):
    event_org = ExternalStaffService.resolve_invite(token)
    if event_org is None:
        return render(request, 'events/staffing/invite_inactive.html', status=404)

    own = event_org.members.filter(source=StaffMember.SOURCE_LINK).select_related('role')
    editing = None
    edit_pk = request.GET.get('edit', '')
    if edit_pk.isdigit():
        editing = own.filter(pk=edit_pk, status=StaffMember.STATUS_PENDING).first()

    form = StaffMemberForm(instance=editing, keep_private=True)
    if request.method == 'POST':
        action = request.POST.get('action')
        if action in ('edit', 'remove'):
            member_pk = request.POST.get('member_pk', '')
            member = own.filter(pk=member_pk).first() if member_pk.isdigit() else None
            if member is None:
                raise Http404
        try:
            if action == 'add':
                form = StaffMemberForm(request.POST, request.FILES)
                if form.is_valid():
                    ExternalStaffService.add_member(
                        event_org=event_org, data=form.cleaned_data,
                        source=StaffMember.SOURCE_LINK,
                    )
                    messages.success(request, 'Elemento enviado. Queda pendiente de revisión.')
                    return redirect('events:staff_invite', token=token)
            elif action == 'edit':
                form = StaffMemberForm(request.POST, request.FILES, instance=member, keep_private=True)
                if form.is_valid():
                    ExternalStaffService.update_pending_member(member=member, data=form.cleaned_data)
                    messages.success(request, 'Elemento corregido.')
                    return redirect('events:staff_invite', token=token)
                editing = member
            elif action == 'remove':
                ExternalStaffService.remove_pending_member(member=member)
                messages.success(request, 'Elemento quitado.')
                return redirect('events:staff_invite', token=token)
        except ValidationError as e:
            messages.error(request, ' '.join(e.messages))
            return redirect('events:staff_invite', token=token)

    return render(request, 'events/staffing/invite.html', {
        'event_org': event_org,
        'event': event_org.event,
        'members': own.order_by('full_name'),
        'form': form,
        'editing': editing,
    })


@login_required
def staff_door(request, token):
    member = ExternalStaffService.resolve_badge(token)
    if member is None:
        return render(request, 'events/staffing/door_invalid.html', status=404)
    if not ExternalStaffService.can_operate_door(request.user, member.event):
        raise PermissionDenied

    if request.method == 'POST':
        try:
            ExternalStaffService.record_access(
                member=member, direction=request.POST.get('direction'), user=request.user,
            )
            messages.success(request, 'Registrado.')
        except ValidationError as e:
            messages.error(request, ' '.join(e.messages))
        return redirect('events:staff_door', token=token)

    PiiAuditService.log(
        request=request, target_user=None, access_type='VIEW_EVENT_STAFF',
        field_accessed='photo', notes=f'door staff_member pk={member.pk}',
    )
    return render(request, 'events/staffing/door.html', {
        'member': member,
        'is_inside': ExternalStaffService.is_inside(member),
        'recent': member.access_logs.select_related('recorded_by')[:5],
    })

import logging

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import role_required
from events.forms import EventTeamRegistrationForm
from events.models import Event, EventTeamRegistration
from events.services import EventRegistrationService
from teams.models import Team

logger = logging.getLogger(__name__)


@role_required('COACH', 'HEADCOACH')
def team_register(request, pk):
    event = get_object_or_404(Event, pk=pk)

    team = Team.objects.filter(coach=request.user, is_active=True).first()
    if not team:
        messages.error(request, 'No tienes un equipo activo para registrar.')
        return redirect('events:event_detail', pk=pk)

    if not event.is_registration_open:
        messages.error(request, 'Las inscripciones para este evento no están abiertas.')
        return redirect('events:event_detail', pk=pk)

    form = EventTeamRegistrationForm(event, request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            EventRegistrationService.register_team(
                event=event,
                team=team,
                category=form.cleaned_data['category'],
                registered_by=request.user,
                notes=form.cleaned_data.get('notes', ''),
            )
            messages.success(
                request,
                f'Equipo "{team.name}" registrado correctamente. Pendiente de aprobación.',
            )
            return redirect('events:my_registrations')
        except ValidationError as e:
            messages.error(request, str(e.message if hasattr(e, 'message') else e))

    return render(request, 'events/coach/register_team.html', {
        'event': event, 'team': team, 'form': form,
    })


@role_required('COACH', 'HEADCOACH')
def my_registrations(request):
    team = Team.objects.filter(coach=request.user, is_active=True).first()
    registrations = []
    if team:
        registrations = (
            EventTeamRegistration.objects.filter(team=team)
            .select_related('event', 'category')
            .order_by('-registered_at')
        )
    return render(request, 'events/coach/my_registrations.html', {
        'team': team,
        'registrations': registrations,
    })

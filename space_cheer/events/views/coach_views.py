import logging

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.decorators import role_required
from events.forms import EventTeamRegistrationForm
from events.models import Event, EventCategory, EventTeamRegistration
from events.services import EventRegistrationService
from teams.models import Team

logger = logging.getLogger(__name__)


@role_required('COACH', 'HEADCOACH')
def team_register(request, pk):
    event = get_object_or_404(Event, pk=pk)

    if not event.is_registration_open:
        messages.error(request, 'Las inscripciones para este evento no están abiertas.')
        return redirect('events:event_detail', pk=pk)

    coach_teams = Team.objects.filter(coach=request.user, is_active=True).order_by('name')
    if not coach_teams.exists():
        messages.error(request, 'No tienes equipos activos para registrar.')
        return redirect('events:event_detail', pk=pk)

    # Excluir equipos que ya tienen registro activo (no WITHDRAWN) en este evento
    already_registered_pks = EventTeamRegistration.objects.filter(
        event=event,
        team__in=coach_teams,
    ).exclude(status=EventTeamRegistration.STATUS_WITHDRAWN).values_list('team_id', flat=True)
    available_teams = coach_teams.exclude(pk__in=already_registered_pks)

    if not available_teams.exists():
        messages.info(request, 'Todos tus equipos ya están registrados en este evento.')
        return redirect('events:my_registrations')

    # Selección de equipo: GET param ?team=pk o campo oculto en POST
    team_pk = request.GET.get('team') or request.POST.get('team_pk')
    if team_pk:
        team = get_object_or_404(Team, pk=team_pk, coach=request.user, is_active=True)
        # Verificar que este equipo específico no esté ya registrado
        if team.pk in list(already_registered_pks):
            messages.error(request, f'El equipo "{team.name}" ya está registrado en este evento.')
            return redirect('events:event_detail', pk=pk)
    elif available_teams.count() == 1:
        team = available_teams.first()
    else:
        # Coach con múltiples equipos disponibles → mostrar selector
        return render(request, 'events/coach/register_team.html', {
            'event': event,
            'coach_teams': available_teams,
            'select_team': True,
        })

    # Categorías donde el coach ya tiene otro equipo registrado (no WITHDRAWN) → excluir
    occupied_category_pks = EventTeamRegistration.objects.filter(
        event=event,
        team__coach=request.user,
    ).exclude(status=EventTeamRegistration.STATUS_WITHDRAWN).values_list('category_id', flat=True)

    # Categorías del evento compatibles con la categoría del equipo
    # EventCategory con team_category=None es abierta (aplica a todos los equipos)
    if team.category is not None:
        available_categories = EventCategory.objects.filter(event=event).filter(
            Q(team_category=team.category) | Q(team_category__isnull=True)
        ).exclude(pk__in=occupied_category_pks).order_by('order', 'name')
    else:
        available_categories = EventCategory.objects.filter(event=event).exclude(
            pk__in=occupied_category_pks
        ).order_by('order', 'name')

    if not available_categories.exists():
        messages.error(
            request,
            f'El equipo "{team.name}" no corresponde a ninguna categoría disponible en este evento.',
        )
        return redirect('events:event_detail', pk=pk)

    # Una sola categoría disponible → auto-selección
    auto_category = available_categories.first() if available_categories.count() == 1 else None
    form = EventTeamRegistrationForm(event, team=team, data=request.POST or None)

    if request.method == 'POST':
        if auto_category:
            try:
                EventRegistrationService.register_team(
                    event=event,
                    team=team,
                    category=auto_category,
                    registered_by=request.user,
                    notes=request.POST.get('notes', ''),
                )
                messages.success(request, f'Equipo "{team.name}" registrado. Pendiente de aprobación.')
                return redirect('events:my_registrations')
            except ValidationError as e:
                messages.error(request, str(e.message if hasattr(e, 'message') else e))
        elif form.is_valid():
            try:
                EventRegistrationService.register_team(
                    event=event,
                    team=team,
                    category=form.cleaned_data['category'],
                    registered_by=request.user,
                    notes=form.cleaned_data.get('notes', ''),
                )
                messages.success(request, f'Equipo "{team.name}" registrado. Pendiente de aprobación.')
                return redirect('events:my_registrations')
            except ValidationError as e:
                messages.error(request, str(e.message if hasattr(e, 'message') else e))

    return render(request, 'events/coach/register_team.html', {
        'event': event,
        'team': team,
        'coach_teams': coach_teams,
        'form': form,
        'auto_category': auto_category,
        'available_categories': available_categories,
        'select_team': False,
    })


@role_required('COACH', 'HEADCOACH')
@require_POST
def registration_withdraw(request, reg_pk):
    registration = get_object_or_404(
        EventTeamRegistration.objects.select_related('team', 'event'),
        pk=reg_pk,
        team__coach=request.user,
    )
    try:
        EventRegistrationService.withdraw_registration(registration=registration, user=request.user)
        messages.success(
            request,
            f'Registro de "{registration.team.name}" en "{registration.event.name}" cancelado.',
        )
    except (ValidationError, PermissionDenied) as e:
        messages.error(request, str(e.message if hasattr(e, 'message') else e))
    return redirect('events:my_registrations')


@role_required('COACH', 'HEADCOACH')
def my_registrations(request):
    coach_teams = Team.objects.filter(coach=request.user, is_active=True).order_by('name')
    registrations = (
        EventTeamRegistration.objects.filter(team__in=coach_teams)
        .select_related('event', 'category', 'team')
        .order_by('-registered_at')
    )
    return render(request, 'events/coach/my_registrations.html', {
        'coach_teams': coach_teams,
        'registrations': registrations,
    })

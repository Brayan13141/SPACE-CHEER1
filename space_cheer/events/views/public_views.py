import logging

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from events.models import Event, EventCategory, EventResult, EventStaffAssignment
from events.services import EventService

logger = logging.getLogger(__name__)


@login_required
def event_list(request):
    filter_status = request.GET.get('filter', '')
    events = Event.objects.select_related('organizer').order_by('-start_date')

    if filter_status == 'upcoming':
        today = timezone.now().date()
        events = events.filter(start_date__gte=today).exclude(status='CANCELLED')
    elif filter_status in [s[0] for s in Event.STATUS_CHOICES]:
        events = events.filter(status=filter_status)

    return render(request, 'events/event_list.html', {
        'events': events,
        'filter_status': filter_status,
        'status_choices': Event.STATUS_CHOICES,
    })


@login_required
def event_detail(request, pk):
    event = get_object_or_404(Event.objects.select_related('organizer'), pk=pk)
    categories = (
        event.categories
        .prefetch_related('registrations')
        .order_by('order', 'name')
    )

    is_admin = (
        request.user.is_superuser
        or request.user.roles.filter(name='ADMIN').exists()
    )
    is_judge = EventStaffAssignment.objects.filter(
        event=event, user=request.user, role__is_judge=True
    ).exists()

    results_qs = (
        EventResult.objects
        .filter(team_registration__event=event)
        .select_related('team_registration__team', 'category')
    )
    if not is_admin:
        results_qs = results_qs.filter(published=True)

    transitions = EventService.get_transition_readiness(event) if is_admin else []

    # Pasos del flujo para el indicador visual (estado: current/done/future/cancelled)
    _STEP_ORDER = [
        ('DRAFT',               'Borrador'),
        ('REGISTRATION_OPEN',   'Inscripciones'),
        ('REGISTRATION_CLOSED', 'Cerrado'),
        ('IN_PROGRESS',         'En Curso'),
        ('COMPLETED',           'Completado'),
    ]
    is_cancelled = event.status == 'CANCELLED'
    try:
        current_idx = [s for s, _ in _STEP_ORDER].index(event.status)
    except ValueError:
        current_idx = -1  # CANCELLED no está en el flujo lineal

    workflow_steps = []
    for idx, (status_key, label) in enumerate(_STEP_ORDER):
        if is_cancelled:
            state = 'cancelled'
        elif idx < current_idx:
            state = 'done'
        elif idx == current_idx:
            state = 'current'
        else:
            state = 'future'
        workflow_steps.append({'num': idx + 1, 'label': label, 'state': state})

    return render(request, 'events/event_detail.html', {
        'event': event,
        'categories': categories,
        'results': results_qs.order_by('category__order', 'placement'),
        'is_admin': is_admin,
        'is_judge': is_judge,
        'transitions': transitions,
        'workflow_steps': workflow_steps,
        'is_cancelled': is_cancelled,
    })

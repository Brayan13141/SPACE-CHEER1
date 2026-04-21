import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.decorators import role_required
from events.forms import (
    EventCategoryForm,
    EventForm,
    EventJudgeAssignmentForm,
    EventJudgingCriteriaForm,
    EventScoreForm,
    EventStaffAssignmentForm,
    RejectRegistrationForm,
)
from events.models import (
    Event,
    EventCategory,
    EventJudgingCriteria,
    EventResult,
    EventScore,
    EventStaffAssignment,
    EventTeamRegistration,
)
from events.services import EventRegistrationService, EventScoringService, EventService

logger = logging.getLogger(__name__)


@role_required('ADMIN')
def event_create(request):
    form = EventForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        try:
            data = form.cleaned_data.copy()
            event = EventService.create_event(
                name=data.pop('name'),
                organizer=request.user,
                event_type=data.pop('event_type'),
                start_date=data.pop('start_date'),
                end_date=data.pop('end_date'),
                **data,
            )
            messages.success(request, f'Evento "{event.name}" creado correctamente.')
            return redirect('events:event_detail', pk=event.pk)
        except ValidationError as e:
            messages.error(request, str(e.message if hasattr(e, 'message') else e))
    return render(request, 'events/event_form.html', {'form': form, 'is_edit': False})


@role_required('ADMIN')
def event_edit(request, pk):
    event = get_object_or_404(Event, pk=pk)
    form = EventForm(request.POST or None, request.FILES or None, instance=event)
    if request.method == 'POST' and form.is_valid():
        try:
            form.save()
            messages.success(request, 'Evento actualizado correctamente.')
            return redirect('events:event_detail', pk=event.pk)
        except ValidationError as e:
            messages.error(request, str(e.message if hasattr(e, 'message') else e))
    return render(request, 'events/event_form.html', {
        'form': form, 'event': event, 'is_edit': True,
    })


@role_required('ADMIN')
def event_status(request, pk):
    if request.method != 'POST':
        return redirect('events:event_detail', pk=pk)
    event = get_object_or_404(Event, pk=pk)
    new_status = request.POST.get('new_status', '')
    try:
        EventService.transition_status(event=event, new_status=new_status, user=request.user)
        messages.success(request, f'Estado cambiado a "{event.get_status_display()}".')
    except (ValidationError, PermissionDenied) as e:
        messages.error(request, str(e))
    return redirect('events:event_detail', pk=pk)


@role_required('ADMIN')
def registrations_list(request, pk):
    event = get_object_or_404(Event, pk=pk)
    registrations = (
        EventTeamRegistration.objects.filter(event=event)
        .select_related('team', 'category', 'registered_by')
        .order_by('status', 'registered_at')
    )
    return render(request, 'events/admin/registrations.html', {
        'event': event,
        'registrations': registrations,
        'reject_form': RejectRegistrationForm(),
    })


@role_required('ADMIN')
def registration_accept(request, pk, reg_pk):
    if request.method != 'POST':
        return redirect('events:registrations_list', pk=pk)
    registration = get_object_or_404(EventTeamRegistration, pk=reg_pk, event_id=pk)
    try:
        EventRegistrationService.accept_registration(
            registration=registration, user=request.user
        )
        messages.success(request, f'Registro de "{registration.team}" aceptado.')
    except (ValidationError, PermissionDenied) as e:
        messages.error(request, str(e))
    return redirect('events:registrations_list', pk=pk)


@role_required('ADMIN')
def registration_reject(request, pk, reg_pk):
    if request.method != 'POST':
        return redirect('events:registrations_list', pk=pk)
    registration = get_object_or_404(EventTeamRegistration, pk=reg_pk, event_id=pk)
    form = RejectRegistrationForm(request.POST)
    if form.is_valid():
        try:
            EventRegistrationService.reject_registration(
                registration=registration,
                user=request.user,
                notes=form.cleaned_data.get('notes', ''),
            )
            messages.success(request, f'Registro de "{registration.team}" rechazado.')
        except (ValidationError, PermissionDenied) as e:
            messages.error(request, str(e))
    return redirect('events:registrations_list', pk=pk)


@role_required('ADMIN')
def staff_manage(request, pk):
    event = get_object_or_404(Event, pk=pk)
    staff_form = EventStaffAssignmentForm(
        request.POST or None, prefix='staff'
    ) if request.POST.get('action') in (None, 'add_staff') else EventStaffAssignmentForm(prefix='staff')
    judge_form = EventJudgeAssignmentForm(
        request.POST or None, prefix='judge'
    ) if request.POST.get('action') == 'add_judge' else EventJudgeAssignmentForm(prefix='judge')

    if request.method == 'POST':
        action = request.POST.get('action', 'add_staff')

        if action == 'delete':
            assignment_pk = request.POST.get('assignment_pk')
            EventStaffAssignment.objects.filter(pk=assignment_pk, event=event).delete()
            messages.success(request, 'Asignación removida.')
            return redirect('events:staff_manage', pk=pk)

        if action == 'add_staff':
            staff_form = EventStaffAssignmentForm(request.POST, prefix='staff')
            if staff_form.is_valid():
                try:
                    assignment = staff_form.save(commit=False)
                    assignment.event = event
                    assignment.assigned_by = request.user
                    assignment.save()
                    messages.success(request, 'Staff asignado correctamente.')
                except ValidationError as e:
                    messages.error(request, str(e))
            return redirect('events:staff_manage', pk=pk)

        if action == 'add_judge':
            judge_form = EventJudgeAssignmentForm(request.POST, prefix='judge')
            if judge_form.is_valid():
                try:
                    assignment = judge_form.save(commit=False)
                    assignment.event = event
                    assignment.assigned_by = request.user
                    assignment.save()
                    messages.success(request, 'Juez asignado correctamente.')
                except ValidationError as e:
                    messages.error(request, str(e))
            return redirect('events:staff_manage', pk=pk)

    staff = (
        EventStaffAssignment.objects.filter(event=event, role__is_judge=False)
        .select_related('user', 'role')
        .order_by('role__name', 'user__first_name')
    )
    judges = (
        EventStaffAssignment.objects.filter(event=event, role__is_judge=True)
        .select_related('user', 'role')
        .order_by('user__first_name')
    )
    return render(request, 'events/admin/staff_manage.html', {
        'event': event,
        'staff_form': staff_form,
        'judge_form': judge_form,
        'staff': staff,
        'judges': judges,
    })


@role_required('ADMIN')
def criteria_manage(request, pk):
    event = get_object_or_404(Event, pk=pk)
    cat_form = EventCategoryForm(event, request.POST or None, prefix='cat')
    crit_form = EventJudgingCriteriaForm(request.POST or None, prefix='crit')

    if request.method == 'POST':
        action = request.POST.get('action', '')

        if action == 'add_category' and cat_form.is_valid():
            try:
                cat = cat_form.save(commit=False)
                cat.event = event
                cat.save()
                messages.success(request, f'Categoría "{cat.name}" creada.')
                return redirect('events:criteria_manage', pk=pk)
            except ValidationError as e:
                messages.error(request, str(e))

        elif action == 'add_criteria' and crit_form.is_valid():
            try:
                crit = crit_form.save(commit=False)
                crit.event = event
                crit.save()
                messages.success(request, f'Criterio "{crit.name}" creado.')
                return redirect('events:criteria_manage', pk=pk)
            except ValidationError as e:
                messages.error(request, str(e))

        elif action == 'delete_category':
            EventCategory.objects.filter(pk=request.POST.get('category_pk'), event=event).delete()
            messages.success(request, 'Categoría eliminada.')
            return redirect('events:criteria_manage', pk=pk)

        elif action == 'delete_criteria':
            EventJudgingCriteria.objects.filter(
                pk=request.POST.get('criteria_pk'), event=event
            ).delete()
            messages.success(request, 'Criterio eliminado.')
            return redirect('events:criteria_manage', pk=pk)

    categories = event.categories.order_by('order', 'name')
    criteria = EventJudgingCriteria.objects.filter(event=event).order_by('order')
    return render(request, 'events/admin/criteria_manage.html', {
        'event': event,
        'cat_form': cat_form,
        'crit_form': crit_form,
        'categories': categories,
        'criteria': criteria,
    })


@login_required
def score_entry(request, pk):
    event = get_object_or_404(Event, pk=pk)
    is_admin = (
        request.user.is_superuser
        or request.user.roles.filter(name='ADMIN').exists()
    )
    is_judge = EventStaffAssignment.objects.filter(
        event=event,
        user=request.user,
        role__name__icontains='juez',
    ).exists() or EventStaffAssignment.objects.filter(
        event=event,
        user=request.user,
        role__name__icontains='judge',
    ).exists()

    if not is_admin and not is_judge:
        messages.error(request, 'No tienes permiso para ingresar scores en este evento.')
        return redirect('events:event_detail', pk=pk)

    form = EventScoreForm(event, request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            EventScoringService.submit_score(
                team_registration=form.cleaned_data['team_registration'],
                criteria=form.cleaned_data['criteria'],
                judge=request.user,
                score=form.cleaned_data['score'],
                round=form.cleaned_data['round'],
                notes=form.cleaned_data.get('notes', ''),
            )
            messages.success(request, 'Score registrado.')
            return redirect('events:score_entry', pk=pk)
        except ValidationError as e:
            messages.error(request, str(e))

    scores = (
        EventScore.objects.filter(team_registration__event=event)
        .select_related('team_registration__team', 'criteria', 'judge')
        .order_by('round', 'criteria__order', 'team_registration__team__name')
    )
    return render(request, 'events/admin/score_entry.html', {
        'event': event, 'form': form, 'scores': scores, 'is_admin': is_admin,
    })


@role_required('ADMIN')
def results_manage(request, pk):
    event = get_object_or_404(Event, pk=pk)

    if request.method == 'POST':
        action = request.POST.get('action', '')

        if action == 'compute':
            reg = get_object_or_404(EventTeamRegistration, pk=request.POST.get('registration_pk'))
            cat = get_object_or_404(EventCategory, pk=request.POST.get('category_pk'))
            try:
                EventScoringService.compute_result(
                    team_registration=reg,
                    category=cat,
                    round=request.POST.get('round', 'FINAL'),
                )
                messages.success(request, 'Resultado calculado.')
            except ValidationError as e:
                messages.error(request, str(e))

        elif action == 'set_placement':
            result = get_object_or_404(EventResult, pk=request.POST.get('result_pk'))
            try:
                result.placement = int(request.POST.get('placement', 0))
                result.save(update_fields=['placement'])
                messages.success(request, 'Lugar actualizado.')
            except (ValueError, ValidationError) as e:
                messages.error(request, str(e))

        elif action == 'publish':
            result = get_object_or_404(EventResult, pk=request.POST.get('result_pk'))
            result.published = True
            result.published_at = timezone.now()
            result.save(update_fields=['published', 'published_at'])
            messages.success(request, 'Resultado publicado.')

        elif action == 'unpublish':
            result = get_object_or_404(EventResult, pk=request.POST.get('result_pk'))
            result.published = False
            result.published_at = None
            result.save(update_fields=['published', 'published_at'])
            messages.success(request, 'Resultado despublicado.')

        return redirect('events:results_manage', pk=pk)

    results = (
        EventResult.objects.filter(team_registration__event=event)
        .select_related('team_registration__team', 'category')
        .order_by('category__order', 'round', 'placement')
    )
    registrations = (
        EventTeamRegistration.objects.filter(event=event, status='ACCEPTED')
        .select_related('team', 'category')
    )
    return render(request, 'events/admin/results_manage.html', {
        'event': event,
        'categories': event.categories.order_by('order', 'name'),
        'results': results,
        'registrations': registrations,
    })

import json
import logging
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from events.models import (
    Event,
    EventJudgingCriteria,
    EventResult,
    EventScore,
    EventStaffAssignment,
    EventTeamRegistration,
)
from events.services import EventScoringService

logger = logging.getLogger(__name__)


def _get_judge_assignment(event, user):
    """Retorna el EventStaffAssignment si el usuario es juez asignado en este evento."""
    return EventStaffAssignment.objects.filter(
        event=event,
        user=user,
        role__is_judge=True,
    ).select_related('role').first()


@login_required
def judge_panel(request, pk):
    """Panel principal del juez para un evento — evaluación en tiempo real."""
    event = get_object_or_404(Event, pk=pk)

    assignment = _get_judge_assignment(event, request.user)
    is_admin = request.user.is_superuser or request.user.roles.filter(name='ADMIN').exists()

    if not assignment and not is_admin:
        messages.error(request, 'No estás asignado como juez en este evento.')
        return redirect('events:event_detail', pk=pk)

    registrations = (
        EventTeamRegistration.objects.filter(event=event, status='ACCEPTED')
        .select_related('team', 'category')
        .order_by('category__order', 'team__name')
    )

    criteria = EventJudgingCriteria.objects.filter(
        event=event, is_active=True
    ).order_by('order')

    # Scores previos del juez actual (todos los rounds)
    my_scores = {}
    for score in EventScore.objects.filter(
        team_registration__event=event,
        judge=request.user,
    ).select_related('team_registration', 'criteria'):
        key = f"{score.team_registration_id}_{score.criteria_id}_{score.round}"
        my_scores[key] = str(score.score)

    return render(request, 'events/judge/panel.html', {
        'event': event,
        'assignment': assignment,
        'registrations': registrations,
        'criteria': criteria,
        'my_scores_json': json.dumps(my_scores),
    })


@login_required
@require_POST
def judge_score_submit(request, pk):
    """Endpoint AJAX — envía o actualiza un score desde el panel del juez."""
    event = get_object_or_404(Event, pk=pk)

    assignment = _get_judge_assignment(event, request.user)
    is_admin = request.user.is_superuser or request.user.roles.filter(name='ADMIN').exists()

    if not assignment and not is_admin:
        return JsonResponse({'ok': False, 'error': 'Sin permiso de juez en este evento.'}, status=403)

    try:
        data = json.loads(request.body)
        reg_pk = int(data['registration_id'])
        criteria_pk = int(data['criteria_id'])
        score_val = Decimal(str(data['score']))
        round_val = data.get('round', EventScore.ROUND_FINAL)
        notes = data.get('notes', '')
    except (KeyError, ValueError, InvalidOperation) as e:
        return JsonResponse({'ok': False, 'error': f'Datos inválidos: {e}'}, status=400)

    registration = get_object_or_404(
        EventTeamRegistration, pk=reg_pk, event=event, status='ACCEPTED'
    )
    criteria = get_object_or_404(
        EventJudgingCriteria, pk=criteria_pk, event=event, is_active=True
    )

    try:
        score_obj = EventScoringService.submit_score(
            team_registration=registration,
            criteria=criteria,
            judge=request.user,
            score=score_val,
            round=round_val,
            notes=notes,
        )
        return JsonResponse({
            'ok': True,
            'score': str(score_obj.score),
            'scored_at': score_obj.scored_at.isoformat(),
        })
    except (ValidationError, PermissionDenied) as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


@login_required
def judge_leaderboard_api(request, pk):
    """Endpoint AJAX — leaderboard en tiempo real con puntajes ponderados actuales."""
    event = get_object_or_404(Event, pk=pk)

    assignment = _get_judge_assignment(event, request.user)
    is_admin = request.user.is_superuser or request.user.roles.filter(name='ADMIN').exists()

    if not assignment and not is_admin:
        return JsonResponse({'error': 'Sin acceso.'}, status=403)

    round_val = request.GET.get('round', EventScore.ROUND_FINAL)

    scores = (
        EventScore.objects.filter(
            team_registration__event=event,
            round=round_val,
            criteria__is_active=True,
        )
        .select_related('team_registration__team', 'team_registration__category', 'criteria')
    )

    # Agrupar scores por equipo y calcular promedio ponderado
    totals = {}
    for s in scores:
        tr_id = s.team_registration_id
        if tr_id not in totals:
            totals[tr_id] = {
                'team': s.team_registration.team.name,
                'category': s.team_registration.category.name,
                'weighted_sum': Decimal('0'),
                'total_weight': Decimal('0'),
            }
        totals[tr_id]['weighted_sum'] += s.score * s.criteria.weight
        totals[tr_id]['total_weight'] += s.criteria.weight

    leaderboard = []
    for data in totals.values():
        avg = (data['weighted_sum'] / data['total_weight']) if data['total_weight'] else Decimal('0')
        leaderboard.append({
            'team': data['team'],
            'category': data['category'],
            'total_score': float(round(avg, 2)),
        })

    leaderboard.sort(key=lambda x: (-x['total_score'], x['team']))
    for i, item in enumerate(leaderboard, 1):
        item['rank'] = i

    return JsonResponse({'leaderboard': leaderboard, 'round': round_val})

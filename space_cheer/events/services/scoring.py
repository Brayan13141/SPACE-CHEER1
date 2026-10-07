"""Calificación: puntajes de los jueces, resultados y tabla de posiciones."""

import logging
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from events.models import Event, EventResult, EventScore

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# EventScoringService
# ---------------------------------------------------------------------------

class EventScoringService:

    @classmethod
    @transaction.atomic
    def submit_score(
        cls, *, team_registration, criteria, judge, score, round='FINAL', notes=''
    ) -> EventScore:
        event = team_registration.event

        # Solo se califica con el evento en curso: antes no ha empezado, y
        # después los resultados publicados quedarían desfasados.
        if event.status != Event.STATUS_IN_PROGRESS:
            raise ValidationError(
                f'Solo se puede calificar con el evento en curso; '
                f'está "{event.get_status_display()}".'
            )

        # Validate judge assignment only when staff assignments exist (skip in dev mode)
        if event.staff_assignments.exists():
            is_judge = event.staff_assignments.filter(
                user=judge,
                role__is_judge=True,
            ).exists()
            is_admin = judge.is_superuser or judge.roles.filter(name='ADMIN').exists()
            if not is_judge and not is_admin:
                raise PermissionDenied(
                    'El usuario no tiene una asignación activa de juez para este evento.'
                )

        # Upsert: update existing score or create a new one
        score_obj, created = EventScore.objects.update_or_create(
            team_registration=team_registration,
            criteria=criteria,
            judge=judge,
            round=round,
            defaults={'score': score, 'notes': notes},
        )
        action = 'created' if created else 'updated'
        logger.info(
            'EventScore %s: team_registration=%s criteria=%s judge=%s round=%s score=%s',
            action, team_registration.pk, criteria.pk, judge, round, score,
        )
        return score_obj

    @classmethod
    @transaction.atomic
    def compute_result(cls, *, team_registration, category, round='FINAL') -> EventResult:
        # Fetch all scores for active criteria belonging to this registration/round
        scores = EventScore.objects.filter(
            team_registration=team_registration,
            round=round,
            criteria__is_active=True,
        ).select_related('criteria')

        # Weighted average: sum(score * weight) / sum(weight)
        total_weight = Decimal('0')
        weighted_sum = Decimal('0')
        for s in scores:
            w = s.criteria.weight
            weighted_sum += s.score * w
            total_weight += w

        total_score = (weighted_sum / total_weight) if total_weight else Decimal('0')

        # placement es obligatorio: un resultado nuevo entra con un lugar
        # provisional y el reordenamiento de abajo le da el definitivo.
        result, created = EventResult.objects.update_or_create(
            team_registration=team_registration,
            category=category,
            round=round,
            defaults={'total_score': total_score},
            create_defaults={'total_score': total_score, 'placement': 1},
        )
        cls._rerank(category=category, round=round)
        result.refresh_from_db()
        action = 'created' if created else 'updated'
        logger.info(
            'EventResult %s: team_registration=%s category=%s round=%s total_score=%s',
            action, team_registration.pk, category.pk, round, total_score,
        )
        return result

    @classmethod
    def _rerank(cls, *, category, round):
        """Reasigna los lugares de la categoría/ronda por puntaje descendente.

        Ranking de competencia: los empates comparten lugar y el siguiente
        salta (8, 8, 5 → 1, 1, 3). Pisa los lugares puestos a mano; el admin
        los ajusta después de calcular si hace falta.
        """
        results = list(
            EventResult.objects.select_for_update()
            .filter(category=category, round=round)
            .order_by('-total_score', 'pk')
        )
        previous_score = None
        placement = 0
        for position, res in enumerate(results, start=1):
            if res.total_score != previous_score:
                placement = position
                previous_score = res.total_score
            if res.placement != placement:
                res.placement = placement
                res.save(update_fields=['placement'])

    @classmethod
    def get_leaderboard(cls, event, category, round='FINAL') -> list:
        # Return published EventResult objects ordered by total_score descending
        return list(
            EventResult.objects.filter(
                category=category,
                round=round,
                published=True,
                team_registration__event=event,
            ).select_related('team_registration', 'team_registration__team')
            .order_by('-total_score')
        )

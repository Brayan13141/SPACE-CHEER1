"""Calificación: criterios, puntajes y resultados."""

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from .core import Event, EventCategory
from .registration import EventTeamRegistration


# ---------------------------------------------------------------------------
# EventJudgingCriteria
# ---------------------------------------------------------------------------

class EventJudgingCriteria(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='judging_criteria')
    name = models.CharField(max_length=100, verbose_name=_('Nombre'))
    description = models.TextField(blank=True, verbose_name=_('Descripción'))
    weight = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('1.00'),
        verbose_name=_('Peso'),
    )
    max_score = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('10.00'),
        verbose_name=_('Puntaje máximo'),
    )
    order = models.PositiveIntegerField(default=0, verbose_name=_('Orden'))
    is_active = models.BooleanField(default=True, verbose_name=_('Activo'))

    class Meta:
        unique_together = [('event', 'name')]
        ordering = ['order']
        verbose_name = _('Criterio de evaluación')
        verbose_name_plural = _('Criterios de evaluación')

    def __str__(self):
        return f'{self.name} ({self.event})'

    def _validate_positive_values(self):
        errors = {}
        if self.weight is not None and self.weight <= 0:
            errors['weight'] = _('El peso debe ser mayor a cero.')
        if self.max_score is not None and self.max_score <= 0:
            errors['max_score'] = _('El puntaje máximo debe ser mayor a cero.')
        if errors:
            raise ValidationError(errors)

    def clean(self):
        self._validate_positive_values()

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


# ---------------------------------------------------------------------------
# EventScore
# ---------------------------------------------------------------------------

class EventScore(models.Model):
    ROUND_PRELIMINARY = 'PRELIMINARY'
    ROUND_FINAL = 'FINAL'

    ROUND_CHOICES = [
        (ROUND_PRELIMINARY, _('Preliminar')),
        (ROUND_FINAL, _('Final')),
    ]

    team_registration = models.ForeignKey(
        EventTeamRegistration,
        on_delete=models.CASCADE,
        related_name='scores',
        verbose_name=_('Registro de equipo'),
    )
    criteria = models.ForeignKey(
        EventJudgingCriteria,
        on_delete=models.PROTECT,
        related_name='scores',
        verbose_name=_('Criterio'),
    )
    judge = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='scores_given',
        verbose_name=_('Juez'),
    )
    score = models.DecimalField(max_digits=5, decimal_places=2, verbose_name=_('Puntaje'))
    round = models.CharField(
        max_length=20, choices=ROUND_CHOICES, default=ROUND_FINAL,
        verbose_name=_('Ronda'),
    )
    notes = models.TextField(blank=True, verbose_name=_('Notas'))
    scored_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('team_registration', 'criteria', 'judge', 'round')]
        verbose_name = _('Puntaje')
        verbose_name_plural = _('Puntajes')

    def __str__(self):
        return f'{self.judge} → {self.team_registration} [{self.criteria}] {self.score}'

    def _validate_score_range(self):
        if self.score is not None and self.criteria_id:
            if self.score < 0:
                raise ValidationError({'score': _('El puntaje no puede ser negativo.')})
            if self.score > self.criteria.max_score:
                raise ValidationError(
                    {'score': _('El puntaje no puede superar el máximo del criterio (%(max)s).') % {'max': self.criteria.max_score}}
                )

    def _validate_criteria_event_match(self):
        if self.criteria_id and self.team_registration_id:
            if self.criteria.event_id != self.team_registration.event_id:
                raise ValidationError(
                    {'criteria': _('El criterio no pertenece al mismo evento que el registro de equipo.')}
                )

    def clean(self):
        self._validate_score_range()
        self._validate_criteria_event_match()

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


# ---------------------------------------------------------------------------
# EventResult
# ---------------------------------------------------------------------------

class EventResult(models.Model):
    ROUND_PRELIMINARY = 'PRELIMINARY'
    ROUND_FINAL = 'FINAL'

    ROUND_CHOICES = [
        (ROUND_PRELIMINARY, _('Preliminar')),
        (ROUND_FINAL, _('Final')),
    ]

    team_registration = models.ForeignKey(
        EventTeamRegistration,
        on_delete=models.CASCADE,
        related_name='results',
    )
    category = models.ForeignKey(
        EventCategory,
        on_delete=models.PROTECT,
        related_name='results',
        verbose_name=_('Categoría'),
    )
    placement = models.PositiveIntegerField(verbose_name=_('Lugar'))
    total_score = models.DecimalField(
        max_digits=7, decimal_places=2, null=True, blank=True,
        verbose_name=_('Puntaje total'),
    )
    round = models.CharField(
        max_length=20, choices=ROUND_CHOICES, default=ROUND_FINAL,
        verbose_name=_('Ronda'),
    )
    notes = models.TextField(blank=True, verbose_name=_('Notas'))
    published = models.BooleanField(default=False, verbose_name=_('Publicado'))
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [('team_registration', 'category', 'round')]
        ordering = ['placement']
        verbose_name = _('Resultado')
        verbose_name_plural = _('Resultados')

    def __str__(self):
        return f'#{self.placement} — {self.team_registration} [{self.category}]'

    def _validate_category_event_match(self):
        if self.category_id and self.team_registration_id:
            if self.category.event_id != self.team_registration.event_id:
                raise ValidationError(
                    {'category': _('La categoría no pertenece al mismo evento que el registro de equipo.')}
                )

    def _validate_placement(self):
        if self.placement is not None and self.placement < 1:
            raise ValidationError({'placement': _('El lugar debe ser 1 o mayor.')})

    def clean(self):
        self._validate_category_event_match()
        self._validate_placement()

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

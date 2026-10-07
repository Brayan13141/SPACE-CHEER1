"""Inscripción: equipos inscritos y sus participantes."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from .core import Event, EventCategory


# ---------------------------------------------------------------------------
# EventTeamRegistration
# ---------------------------------------------------------------------------

class EventTeamRegistration(models.Model):
    STATUS_PENDING = 'PENDING'
    STATUS_ACCEPTED = 'ACCEPTED'
    STATUS_REJECTED = 'REJECTED'
    STATUS_WITHDRAWN = 'WITHDRAWN'

    STATUS_CHOICES = [
        (STATUS_PENDING, _('Pendiente')),
        (STATUS_ACCEPTED, _('Aceptado')),
        (STATUS_REJECTED, _('Rechazado')),
        (STATUS_WITHDRAWN, _('Retirado')),
    ]

    event = models.ForeignKey(Event, on_delete=models.PROTECT, related_name='team_registrations')
    team = models.ForeignKey(
        'teams.Team',
        on_delete=models.PROTECT,
        related_name='event_registrations',
    )
    category = models.ForeignKey(
        EventCategory,
        on_delete=models.PROTECT,
        related_name='registrations',
        verbose_name=_('Categoría'),
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING,
        verbose_name=_('Estado'),
    )
    registered_at = models.DateTimeField(auto_now_add=True)
    registered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='submitted_registrations',
    )
    notes = models.TextField(blank=True, verbose_name=_('Notas'))

    class Meta:
        unique_together = [('event', 'team')]
        verbose_name = _('Registro de equipo')
        verbose_name_plural = _('Registros de equipos')

    def __str__(self):
        return f'{self.team} @ {self.event}'

    def _validate_category_belongs_to_event(self):
        if self.category_id and self.event_id:
            if self.category.event_id != self.event_id:
                raise ValidationError({'category': _('La categoría no pertenece al evento seleccionado.')})

    def clean(self):
        self._validate_category_belongs_to_event()

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


# ---------------------------------------------------------------------------
# EventParticipant
# ---------------------------------------------------------------------------

class EventParticipant(models.Model):
    ROLE_ATHLETE = 'ATHLETE'
    ROLE_HEADCOACH = 'HEADCOACH'
    ROLE_COACH = 'COACH'
    ROLE_STAFF = 'STAFF'
    ROLE_GUARDIAN = 'GUARDIAN'
    ROLE_GUEST = 'GUEST'

    ROLE_CHOICES = [
        (ROLE_ATHLETE, _('Atleta')),
        (ROLE_HEADCOACH, _('Head Coach')),
        (ROLE_COACH, _('Coach')),
        (ROLE_STAFF, _('Staff')),
        (ROLE_GUARDIAN, _('Tutor')),
        (ROLE_GUEST, _('Invitado')),
    ]

    STATUS_REGISTERED = 'REGISTERED'
    STATUS_CONFIRMED = 'CONFIRMED'
    STATUS_CANCELLED = 'CANCELLED'

    STATUS_CHOICES = [
        (STATUS_REGISTERED, _('Registrado')),
        (STATUS_CONFIRMED, _('Confirmado')),
        (STATUS_CANCELLED, _('Cancelado')),
    ]

    event = models.ForeignKey(Event, on_delete=models.PROTECT, related_name='participants')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='event_participations',
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_ATHLETE, verbose_name=_('Rol'))
    team_registration = models.ForeignKey(
        EventTeamRegistration,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='participants',
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_REGISTERED,
        verbose_name=_('Estado'),
    )
    registered_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, verbose_name=_('Notas'))

    class Meta:
        unique_together = [('event', 'user')]
        verbose_name = _('Participante')
        verbose_name_plural = _('Participantes')

    def __str__(self):
        return f'{self.user} @ {self.event} ({self.role})'

    def _validate_team_registration_event(self):
        if self.team_registration_id and self.event_id:
            if self.team_registration.event_id != self.event_id:
                raise ValidationError(
                    {'team_registration': _('El registro de equipo no pertenece al evento seleccionado.')}
                )

    def clean(self):
        self._validate_team_registration_event()

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

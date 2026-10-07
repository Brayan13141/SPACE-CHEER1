"""Núcleo del evento: el evento y sus categorías."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


# ---------------------------------------------------------------------------
# Event
# ---------------------------------------------------------------------------

class Event(models.Model):
    STATUS_DRAFT = 'DRAFT'
    STATUS_REGISTRATION_OPEN = 'REGISTRATION_OPEN'
    STATUS_REGISTRATION_CLOSED = 'REGISTRATION_CLOSED'
    STATUS_IN_PROGRESS = 'IN_PROGRESS'
    STATUS_COMPLETED = 'COMPLETED'
    STATUS_CANCELLED = 'CANCELLED'

    STATUS_CHOICES = [
        (STATUS_DRAFT, _('Borrador')),
        (STATUS_REGISTRATION_OPEN, _('Inscripciones abiertas')),
        (STATUS_REGISTRATION_CLOSED, _('Inscripciones cerradas')),
        (STATUS_IN_PROGRESS, _('En progreso')),
        (STATUS_COMPLETED, _('Completado')),
        (STATUS_CANCELLED, _('Cancelado')),
    ]

    TYPE_COMPETITION = 'COMPETITION'
    TYPE_WORKSHOP = 'WORKSHOP'
    TYPE_EXHIBITION = 'EXHIBITION'
    TYPE_FRIENDLY = 'FRIENDLY'

    TYPE_CHOICES = [
        (TYPE_COMPETITION, _('Competencia')),
        (TYPE_WORKSHOP, _('Taller')),
        (TYPE_EXHIBITION, _('Exhibición')),
        (TYPE_FRIENDLY, _('Amistoso')),
    ]

    name = models.CharField(max_length=200, verbose_name=_('Nombre'))
    description = models.TextField(blank=True, verbose_name=_('Descripción'))
    event_type = models.CharField(
        max_length=20, choices=TYPE_CHOICES, default=TYPE_COMPETITION,
        verbose_name=_('Tipo de evento'),
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT,
        verbose_name=_('Estado'),
    )
    organizer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='organized_events',
        verbose_name=_('Organizador'),
    )
    venue_name = models.CharField(max_length=200, blank=True, verbose_name=_('Sede'))
    venue_address = models.CharField(max_length=300, blank=True, verbose_name=_('Dirección'))
    venue_city = models.CharField(max_length=100, blank=True, verbose_name=_('Ciudad'))
    start_date = models.DateField(verbose_name=_('Fecha de inicio'))
    end_date = models.DateField(verbose_name=_('Fecha de fin'))
    registration_open = models.DateField(null=True, blank=True, verbose_name=_('Apertura de inscripciones'))
    registration_close = models.DateField(null=True, blank=True, verbose_name=_('Cierre de inscripciones'))
    max_teams = models.PositiveIntegerField(null=True, blank=True, verbose_name=_('Máx. equipos'))
    banner = models.ImageField(upload_to='events/banners/', null=True, blank=True, verbose_name=_('Banner'))
    featured_on_landing = models.BooleanField(default=False, verbose_name=_('Destacado en landing'))
    landing_order = models.PositiveIntegerField(default=0, verbose_name=_('Orden en landing'))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-start_date']
        verbose_name = _('Evento')
        verbose_name_plural = _('Eventos')
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['start_date']),
            models.Index(fields=['organizer']),
        ]

    def __str__(self):
        return self.name

    def _validate_dates(self):
        errors = {}
        if self.end_date and self.start_date and self.end_date < self.start_date:
            errors['end_date'] = _('La fecha de fin debe ser igual o posterior a la de inicio.')
        if self.registration_open and self.registration_close:
            if self.registration_close < self.registration_open:
                errors['registration_close'] = _('El cierre de inscripciones debe ser igual o posterior a la apertura.')
        if self.registration_close and self.start_date:
            if self.registration_close > self.start_date:
                errors['registration_close'] = _('Las inscripciones deben cerrar antes o el mismo día del evento.')
        if errors:
            raise ValidationError(errors)

    def clean(self):
        self._validate_dates()

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def is_registration_open(self):
        if self.status != self.STATUS_REGISTRATION_OPEN:
            return False
        today = timezone.localdate()
        if self.registration_open and today < self.registration_open:
            return False
        if self.registration_close and today > self.registration_close:
            return False
        return True


# ---------------------------------------------------------------------------
# EventCategory
# ---------------------------------------------------------------------------

class EventCategory(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='categories')
    name = models.CharField(max_length=100, verbose_name=_('Nombre'))
    team_category = models.ForeignKey(
        'teams.TeamCategory',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='event_categories',
        verbose_name=_('Categoría de equipo'),
    )
    max_teams = models.PositiveIntegerField(null=True, blank=True, verbose_name=_('Máx. equipos'))
    description = models.TextField(blank=True, verbose_name=_('Descripción'))
    order = models.PositiveIntegerField(default=0, verbose_name=_('Orden'))

    class Meta:
        unique_together = [('event', 'name')]
        ordering = ['order', 'name']
        verbose_name = _('Categoría de evento')
        verbose_name_plural = _('Categorías de evento')

    def __str__(self):
        return f'{self.event} — {self.name}'

    def clean(self):
        pass

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

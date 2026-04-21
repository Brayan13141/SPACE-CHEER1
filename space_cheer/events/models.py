from decimal import Decimal
import datetime

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
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
        today = datetime.date.today()
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
    ROLE_COACH = 'COACH'
    ROLE_STAFF = 'STAFF'
    ROLE_GUARDIAN = 'GUARDIAN'
    ROLE_GUEST = 'GUEST'

    ROLE_CHOICES = [
        (ROLE_ATHLETE, _('Atleta')),
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


# ---------------------------------------------------------------------------
# EventStaffRole
# ---------------------------------------------------------------------------

class EventStaffRole(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name=_('Nombre'))
    description = models.TextField(blank=True, verbose_name=_('Descripción'))
    is_active = models.BooleanField(default=True, verbose_name=_('Activo'))

    class Meta:
        ordering = ['name']
        verbose_name = _('Rol de staff')
        verbose_name_plural = _('Roles de staff')

    def __str__(self):
        return self.name

    def clean(self):
        pass

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


# ---------------------------------------------------------------------------
# EventStaffAssignment
# ---------------------------------------------------------------------------

class EventStaffAssignment(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='staff_assignments')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='event_staff_roles',
        verbose_name=_('Usuario'),
    )
    role = models.ForeignKey(
        EventStaffRole,
        on_delete=models.PROTECT,
        related_name='assignments',
        verbose_name=_('Rol'),
    )
    notes = models.TextField(blank=True, verbose_name=_('Notas'))
    assigned_at = models.DateTimeField(auto_now_add=True)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='staff_assignments_made',
    )

    class Meta:
        unique_together = [('event', 'user', 'role')]
        verbose_name = _('Asignación de staff')
        verbose_name_plural = _('Asignaciones de staff')

    def __str__(self):
        return f'{self.user} — {self.role} @ {self.event}'

    def clean(self):
        pass

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


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

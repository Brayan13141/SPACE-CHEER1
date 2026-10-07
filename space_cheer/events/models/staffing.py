"""Staff del evento: roles y asignaciones."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .core import Event


# ---------------------------------------------------------------------------
# EventStaffRole
# ---------------------------------------------------------------------------

class EventStaffRole(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name=_('Nombre'))
    description = models.TextField(blank=True, verbose_name=_('Descripción'))
    is_active = models.BooleanField(default=True, verbose_name=_('Activo'))
    is_judge = models.BooleanField(default=False, verbose_name=_('Es rol de juez'))

    class Meta:
        ordering = ['name']
        verbose_name = _('Rol de staff')
        verbose_name_plural = _('Roles de staff')

    def __str__(self):
        return self.name

    def clean(self):
        # `unique=True` distingue mayúsculas: "Coordinador de piso" y
        # "Coordinador de Piso" convivían como dos roles distintos.
        if self.name and (
            EventStaffRole.objects.filter(name__iexact=self.name.strip())
            .exclude(pk=self.pk)
            .exists()
        ):
            raise ValidationError({'name': _('Ya existe un rol de staff con ese nombre.')})

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
        # Un rol desactivado no se asigna de nuevo; las asignaciones que ya
        # tenía siguen editándose.
        if self.role_id and not self.role.is_active:
            role_changed = (
                self.pk is None
                or EventStaffAssignment.objects.filter(pk=self.pk)
                .exclude(role_id=self.role_id)
                .exists()
            )
            if role_changed:
                raise ValidationError({'role': _('Este rol de staff está desactivado.')})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


# ---------------------------------------------------------------------------
# Staff externo (sin cuenta)
# ---------------------------------------------------------------------------

class Organization(models.Model):
    KIND_PUBLIC_INSTITUTION = 'PUBLIC_INSTITUTION'
    KIND_VENDOR = 'VENDOR'
    KIND_ORGANIZER = 'ORGANIZER'
    KIND_CHOICES = [
        (KIND_PUBLIC_INSTITUTION, _('Institución pública')),
        (KIND_VENDOR, _('Proveedor')),
        (KIND_ORGANIZER, _('Organizador')),
    ]

    name = models.CharField(max_length=150, unique=True, verbose_name=_('Nombre'))
    kind = models.CharField(max_length=30, choices=KIND_CHOICES, verbose_name=_('Tipo'))
    contact_name = models.CharField(max_length=150, blank=True, verbose_name=_('Contacto'))
    contact_phone = models.CharField(max_length=20, blank=True, verbose_name=_('Teléfono de contacto'))
    is_active = models.BooleanField(default=True, verbose_name=_('Activa'))

    class Meta:
        ordering = ['name']
        verbose_name = _('Organización')
        verbose_name_plural = _('Organizaciones')

    def __str__(self):
        return self.name

    def clean(self):
        if self.name and (
            Organization.objects.filter(name__iexact=self.name.strip())
            .exclude(pk=self.pk)
            .exists()
        ):
            raise ValidationError({'name': _('Ya existe una organización con ese nombre.')})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class EventOrganization(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='external_organizations')
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT, related_name='event_links')
    invite_nonce = models.CharField(max_length=64, blank=True)
    invite_expires_at = models.DateTimeField(null=True, blank=True)
    invite_revoked_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('event', 'organization')]
        ordering = ['organization__name']
        verbose_name = _('Organización del evento')
        verbose_name_plural = _('Organizaciones del evento')

    def __str__(self):
        return f'{self.organization} @ {self.event}'

    @property
    def invite_is_active(self):
        return bool(
            self.invite_nonce
            and self.invite_revoked_at is None
            and self.invite_expires_at
            and timezone.now() < self.invite_expires_at
        )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class StaffMember(models.Model):
    STATUS_PENDING = 'PENDING'
    STATUS_ACCEPTED = 'ACCEPTED'
    STATUS_REJECTED = 'REJECTED'
    STATUS_CHOICES = [
        (STATUS_PENDING, _('Pendiente')),
        (STATUS_ACCEPTED, _('Aceptado')),
        (STATUS_REJECTED, _('Rechazado')),
    ]

    SOURCE_ADMIN = 'ADMIN'
    SOURCE_LINK = 'LINK'
    SOURCE_CHOICES = [
        (SOURCE_ADMIN, _('Capturado por administración')),
        (SOURCE_LINK, _('Enviado por la organización')),
    ]

    event_organization = models.ForeignKey(
        EventOrganization, on_delete=models.CASCADE, related_name='members',
    )
    full_name = models.CharField(max_length=150, verbose_name=_('Nombre completo'))
    phone = models.CharField(max_length=20, blank=True, verbose_name=_('Teléfono'))
    photo = models.ImageField(upload_to='event_staff/photos/', blank=True, verbose_name=_('Foto'))
    credential = models.CharField(max_length=80, blank=True, verbose_name=_('Placa o credencial'))
    role = models.ForeignKey(
        EventStaffRole, on_delete=models.PROTECT, related_name='external_members',
        verbose_name=_('Función'),
    )
    shift = models.CharField(max_length=80, blank=True, verbose_name=_('Turno'))
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES, default=SOURCE_LINK)
    badge_nonce = models.CharField(max_length=64, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    personal_data_purged_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['full_name']
        verbose_name = _('Elemento de staff externo')
        verbose_name_plural = _('Staff externo')

    def __str__(self):
        return f'{self.full_name} ({self.event_organization.organization})'

    @property
    def event(self):
        return self.event_organization.event

    def clean(self):
        if not self.role_id:
            return
        role_changed = (
            self.pk is None
            or StaffMember.objects.filter(pk=self.pk).exclude(role_id=self.role_id).exists()
        )
        if role_changed:
            if not self.role.is_active:
                raise ValidationError({'role': _('Este rol de staff está desactivado.')})
            if self.role.is_judge:
                raise ValidationError({'role': _('Los jueces necesitan cuenta: asígnalos desde Staff y Jueces.')})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class StaffAccessLog(models.Model):
    DIRECTION_IN = 'IN'
    DIRECTION_OUT = 'OUT'
    DIRECTION_CHOICES = [
        (DIRECTION_IN, _('Entrada')),
        (DIRECTION_OUT, _('Salida')),
    ]

    member = models.ForeignKey(StaffMember, on_delete=models.PROTECT, related_name='access_logs')
    direction = models.CharField(max_length=3, choices=DIRECTION_CHOICES)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+',
    )
    recorded_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-recorded_at', '-pk']
        verbose_name = _('Registro de acceso')
        verbose_name_plural = _('Bitácora de accesos')

    def __str__(self):
        return f'{self.member} {self.direction} {self.recorded_at:%Y-%m-%d %H:%M}'

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ValidationError(_('La bitácora de accesos no se edita.'))
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError(_('La bitácora de accesos no se borra.'))

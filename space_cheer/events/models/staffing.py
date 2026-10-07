"""Staff del evento: roles y asignaciones."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
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

import logging

from django import forms
from django.utils.translation import gettext_lazy as _

from .models import (
    Event,
    EventCategory,
    EventJudgingCriteria,
    EventScore,
    EventStaffAssignment,
    EventStaffRole,
    EventTeamRegistration,
)

logger = logging.getLogger(__name__)


def _bs(field):
    """Apply Bootstrap 5 class to widget."""
    w = field.widget
    if isinstance(w, (forms.Select, forms.SelectMultiple)):
        w.attrs.setdefault('class', 'form-select')
    elif isinstance(w, forms.CheckboxInput):
        w.attrs.setdefault('class', 'form-check-input')
    else:
        w.attrs.setdefault('class', 'form-control')


class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = [
            'name', 'event_type', 'description', 'banner',
            'start_date', 'end_date',
            'registration_open', 'registration_close',
            'venue_name', 'venue_address', 'venue_city',
            'max_teams',
        ]
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
            'registration_open': forms.DateInput(attrs={'type': 'date'}),
            'registration_close': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            _bs(f)


class EventCategoryForm(forms.ModelForm):
    class Meta:
        model = EventCategory
        fields = ['name', 'team_category', 'max_teams', 'description', 'order']

    def __init__(self, event, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.event = event
        for f in self.fields.values():
            _bs(f)


class EventStaffAssignmentForm(forms.ModelForm):
    """Asigna staff general (roles con is_judge=False)."""
    class Meta:
        model = EventStaffAssignment
        fields = ['user', 'role', 'notes']
        widgets = {'notes': forms.Textarea(attrs={'rows': 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from django.apps import apps
        from django.conf import settings
        User = apps.get_model(settings.AUTH_USER_MODEL)
        # Solo usuarios con rol global de tipo staff
        self.fields['user'].queryset = (
            User.objects.filter(is_active=True, roles__is_staff_type=True)
            .distinct().order_by('first_name', 'last_name')
        )
        # Solo roles de staff (no jueces)
        self.fields['role'].queryset = EventStaffRole.objects.filter(
            is_active=True, is_judge=False
        )
        for f in self.fields.values():
            _bs(f)


class EventJudgeAssignmentForm(forms.ModelForm):
    """Asigna jueces (roles con is_judge=True). Usuario debe tener rol global JUEZ."""
    class Meta:
        model = EventStaffAssignment
        fields = ['user', 'role', 'notes']
        widgets = {'notes': forms.Textarea(attrs={'rows': 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from django.apps import apps
        from django.conf import settings
        User = apps.get_model(settings.AUTH_USER_MODEL)
        # Solo usuarios con rol global de tipo juez
        self.fields['user'].queryset = (
            User.objects.filter(is_active=True, roles__is_judge_type=True)
            .distinct().order_by('first_name', 'last_name')
        )
        # Solo roles de juez
        self.fields['role'].queryset = EventStaffRole.objects.filter(
            is_active=True, is_judge=True
        )
        for f in self.fields.values():
            _bs(f)


class EventJudgingCriteriaForm(forms.ModelForm):
    class Meta:
        model = EventJudgingCriteria
        fields = ['name', 'description', 'weight', 'max_score', 'order']
        widgets = {'description': forms.Textarea(attrs={'rows': 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            _bs(f)


class EventTeamRegistrationForm(forms.ModelForm):
    class Meta:
        model = EventTeamRegistration
        fields = ['category', 'notes']
        widgets = {'notes': forms.Textarea(attrs={'rows': 3})}

    def __init__(self, event, team=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from django.db.models import Q
        # Filtrar categorías según la TeamCategory del equipo
        if team is not None and team.category is not None:
            qs = EventCategory.objects.filter(event=event).filter(
                Q(team_category=team.category) | Q(team_category__isnull=True)
            ).order_by('order', 'name')
        else:
            qs = EventCategory.objects.filter(event=event).order_by('order', 'name')
        self.fields['category'].queryset = qs
        for f in self.fields.values():
            _bs(f)


class EventScoreForm(forms.ModelForm):
    class Meta:
        model = EventScore
        fields = ['team_registration', 'criteria', 'score', 'round', 'notes']
        widgets = {'notes': forms.Textarea(attrs={'rows': 2})}

    def __init__(self, event, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['team_registration'].queryset = (
            EventTeamRegistration.objects.filter(event=event, status='ACCEPTED')
            .select_related('team')
        )
        self.fields['criteria'].queryset = (
            EventJudgingCriteria.objects.filter(event=event, is_active=True).order_by('order')
        )
        for f in self.fields.values():
            _bs(f)


class RejectRegistrationForm(forms.Form):
    notes = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        label=_('Motivo del rechazo'),
        required=False,
    )

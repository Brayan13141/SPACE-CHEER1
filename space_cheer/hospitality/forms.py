import logging

from django import forms
from django.conf import settings
from django.apps import apps

from .models import (
    Bed,
    BedAssignment,
    Hotel,
    HospitalityPreference,
    Room,
    RoomAssignment,
    RoomFeature,
    RoomType,
    Stay,
)



logger = logging.getLogger(__name__)


def _bs(field):
    w = field.widget
    if isinstance(w, (forms.Select, forms.SelectMultiple)):
        w.attrs.setdefault('class', 'form-select')
    elif isinstance(w, forms.CheckboxInput):
        w.attrs.setdefault('class', 'form-check-input')
    elif isinstance(w, forms.CheckboxSelectMultiple):
        pass
    else:
        w.attrs.setdefault('class', 'form-control')


class RoomFeatureForm(forms.ModelForm):
    class Meta:
        model = RoomFeature
        fields = ['name', 'icon']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['icon'].help_text = 'Clase Bootstrap Icons, ej: bi-wifi'
        for f in self.fields.values():
            _bs(f)


class HotelForm(forms.ModelForm):
    class Meta:
        model = Hotel
        fields = ['name', 'address', 'city', 'phone', 'website', 'description', 'image', 'is_active']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            _bs(f)


class RoomTypeForm(forms.ModelForm):
    class Meta:
        model = RoomType
        fields = ['name', 'capacity', 'description', 'base_price', 'features']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2}),
            'features': forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            _bs(f)


class RoomForm(forms.ModelForm):
    class Meta:
        model = Room
        fields = ['room_number', 'floor', 'room_type', 'notes', 'is_available']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, hotel, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['room_type'].queryset = RoomType.objects.filter(hotel=hotel)
        for f in self.fields.values():
            _bs(f)


class BedForm(forms.ModelForm):
    class Meta:
        model = Bed
        fields = ['bed_type', 'label', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            _bs(f)


class StayCreateForm(forms.Form):
    user = forms.ModelChoiceField(
        queryset=None,
        label='Participante',
        help_text='Usuario que tendrá la estancia',
    )
    notes = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 2}),
        required=False,
        label='Notas',
    )

    def __init__(self, event, *args, **kwargs):
        super().__init__(*args, **kwargs)
        User = apps.get_model(settings.AUTH_USER_MODEL)
        existing_stay_user_ids = Stay.objects.filter(event=event).values_list('user_id', flat=True)
        self.fields['user'].queryset = (
            User.objects.filter(is_active=True)
            .exclude(pk__in=existing_stay_user_ids)
            .order_by('first_name', 'last_name')
        )
        for f in self.fields.values():
            _bs(f)


class StayConfirmForm(forms.Form):
    hotel = forms.ModelChoiceField(queryset=None, label='Hotel')
    check_in_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        label='Fecha de check-in',
    )
    check_out_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        label='Fecha de check-out',
    )

    def __init__(self, event, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['hotel'].queryset = Hotel.objects.filter(event=event, is_active=True)
        for f in self.fields.values():
            _bs(f)

    def clean(self):
        cleaned = super().clean()
        check_in = cleaned.get('check_in_date')
        check_out = cleaned.get('check_out_date')
        if check_in and check_out and check_out <= check_in:
            raise forms.ValidationError('La fecha de check-out debe ser posterior al check-in.')
        return cleaned


class RoomAssignForm(forms.Form):
    room = forms.ModelChoiceField(queryset=None, label='Habitación')
    notes = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 2}),
        required=False,
        label='Notas',
    )

    def __init__(self, hotel, exclude_stay=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from .services import RoomAssignmentService
        self.fields['room'].queryset = RoomAssignmentService.get_available_rooms(
            hotel, exclude_stay=exclude_stay
        ).select_related('room_type')
        for f in self.fields.values():
            _bs(f)


class BedAssignForm(forms.Form):
    bed = forms.ModelChoiceField(queryset=None, label='Cama')
    notes = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 2}),
        required=False,
        label='Notas',
    )

    def __init__(self, room, *args, **kwargs):
        super().__init__(*args, **kwargs)
        occupied_bed_ids = BedAssignment.objects.filter(
            bed__room=room
        ).exclude(
            stay__status=Stay.CANCELLED
        ).values_list('bed_id', flat=True)
        self.fields['bed'].queryset = Bed.objects.filter(
            room=room
        ).exclude(pk__in=occupied_bed_ids)
        for f in self.fields.values():
            _bs(f)


class HospitalityPreferenceForm(forms.ModelForm):
    class Meta:
        model = HospitalityPreference
        fields = [
            'preferred_hotel', 'preferred_room_type',
            'preferred_features', 'roommate_preferences',
            'special_needs', 'notes',
        ]
        widgets = {
            'special_needs': forms.Textarea(attrs={'rows': 3}),
            'notes': forms.Textarea(attrs={'rows': 2}),
            'preferred_features': forms.CheckboxSelectMultiple(),
            'roommate_preferences': forms.CheckboxSelectMultiple(),
        }

    def __init__(self, event, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['preferred_hotel'].queryset = Hotel.objects.filter(event=event, is_active=True)
        self.fields['preferred_room_type'].queryset = RoomType.objects.filter(hotel__event=event)
        self.fields['roommate_preferences'].queryset = self._roommate_qs(event, user)
        self.fields['roommate_preferences'].help_text = (
            'Solo tus alumnos a cargo aparecen como opciones.'
            if user.roles.filter(name='GUARDIAN').exists()
            else 'Solo miembros activos de tu equipo registrado en este evento.'
        )
        self.fields['preferred_hotel'].required = False
        self.fields['preferred_room_type'].required = False
        for f in self.fields.values():
            _bs(f)

    @staticmethod
    def _roommate_qs(event, user):
        User = apps.get_model(settings.AUTH_USER_MODEL)
        from events.models import EventTeamRegistration  # inline — evita importación circular
        from teams.models import UserTeamMembership, Team

        # ── Guardianes: solo sus alumnos a cargo ─────────────────────────────
        if user.roles.filter(name='GUARDIAN').exists():
            return (
                User.objects
                .filter(is_active=True, athleteprofile__guardian=user)
                .distinct()
                .exclude(pk=user.pk)
                .order_by('first_name', 'last_name')
            )

        # ── Todos los demás: miembros del mismo equipo en este evento ─────────
        # Equipos inscritos al evento (cualquier estado — las preferencias se
        # pueden registrar antes de que la inscripción sea confirmada)
        event_team_ids = EventTeamRegistration.objects.filter(
            event=event
        ).values_list('team_id', flat=True)

        # Equipos del usuario como miembro aceptado
        member_team_ids = (
            UserTeamMembership.objects
            .filter(
                user=user,
                team_id__in=event_team_ids,
                status='accepted',
                is_active=True,
            )
            .values_list('team_id', flat=True)
        )

        # Equipos del usuario como entrenador principal (Team.coach FK)
        coached_team_ids = (
            Team.objects
            .filter(coach=user, pk__in=event_team_ids)
            .values_list('pk', flat=True)
        )

        user_team_ids = list(set(list(member_team_ids) + list(coached_team_ids)))

        if not user_team_ids:
            return User.objects.none()

        # Todos los miembros activos y aceptados de esos equipos (atletas + staff)
        return (
            User.objects
            .filter(
                is_active=True,
                team_memberships__team_id__in=user_team_ids,
                team_memberships__status='accepted',
                team_memberships__is_active=True,
            )
            .distinct()
            .exclude(pk=user.pk)
            .order_by('first_name', 'last_name')
        )

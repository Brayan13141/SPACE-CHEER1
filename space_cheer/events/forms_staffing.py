# events/forms_staffing.py
from django import forms
from django.core.exceptions import ValidationError

from events.models import EventStaffRole, Organization, StaffMember
from orders.services.file_validation import FileValidator


class OrganizationForm(forms.ModelForm):
    class Meta:
        model = Organization
        fields = ['name', 'kind', 'contact_name', 'contact_phone']


class LinkOrganizationForm(forms.Form):
    organization = forms.ModelChoiceField(queryset=Organization.objects.none(), label='Organización')

    def __init__(self, *args, event=None, **kwargs):
        super().__init__(*args, **kwargs)
        qs = Organization.objects.filter(is_active=True)
        if event is not None:
            qs = qs.exclude(event_links__event=event)
        self.fields['organization'].queryset = qs.order_by('name')


class StaffMemberForm(forms.ModelForm):
    class Meta:
        model = StaffMember
        fields = ['full_name', 'phone', 'photo', 'credential', 'role', 'shift']

    def __init__(self, *args, keep_private=False, **kwargs):
        """keep_private=True (enlace público): no devuelve el teléfono ni la
        foto actual; teléfono en blanco = conservar el guardado."""
        super().__init__(*args, **kwargs)
        # Sin enlace "Actualmente" ni casilla "Limpiar": el archivo solo se
        # reemplaza, nunca se borra desde el formulario.
        self.fields['photo'].widget = forms.FileInput()
        self.keep_private = keep_private and bool(self.instance and self.instance.pk)
        if self.keep_private:
            self.initial['phone'] = ''
        # Jueces tienen cuenta y se asignan desde Staff y Jueces.
        self.fields['role'].queryset = EventStaffRole.objects.filter(
            is_active=True, is_judge=False,
        ).order_by('name')
        # La foto se exige al capturar; al corregir se conserva la que hay.
        self.fields['photo'].required = not (self.instance and self.instance.photo)

    def clean_phone(self):
        phone = self.cleaned_data.get('phone', '')
        if self.keep_private and not phone:
            return self.instance.phone
        return phone

    def clean_photo(self):
        photo = self.cleaned_data.get('photo')
        if photo and hasattr(photo, 'content_type'):  # archivo recién subido
            try:
                FileValidator.validate_image(photo)
            except ValidationError as e:
                raise ValidationError(e.messages)
        return photo

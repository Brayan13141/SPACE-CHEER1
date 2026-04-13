# accounts/forms_profile.py
"""
Formularios para edición de perfil.

Estos formularios se agregan a accounts/forms.py o se importan desde ahí.
Los separamos aquí para claridad de fase.

Instrucciones de integración:
    En accounts/forms.py, agregar al final:
    from accounts.forms_profile import ProfileEditForm, ProfilePhotoForm
    __all__ = [..., "ProfileEditForm", "ProfilePhotoForm"]
"""

from django import forms
from django.contrib.auth import get_user_model

User = get_user_model()


class ProfileEditForm(forms.ModelForm):
    """
    Formulario para que el usuario edite sus propios datos básicos.

    NO incluye: email (flujo separado via allauth), CURP (flujo separado),
    username (inmutable), roles (solo admin).

    Incluye validación de teléfono (ya definida en User.clean()).
    """

    class Meta:
        model = User
        fields = ["first_name", "last_name", "phone", "birth_date", "gender"]
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
            "phone": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "10 dígitos sin espacios",
                    "maxlength": "10",
                }
            ),
            "birth_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"},
                format="%Y-%m-%d",
            ),
            "gender": forms.Select(
                attrs={"class": "form-select"},
                choices=[("", "Prefiero no decir")] + list(User.gender.field.choices),
            ),
        }
        labels = {
            "first_name": "Nombre(s)",
            "last_name": "Apellidos",
            "phone": "Teléfono",
            "birth_date": "Fecha de nacimiento",
            "gender": "Género",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # birth_date necesita input_formats para renderizar correctamente
        self.fields["birth_date"].input_formats = ["%Y-%m-%d"]
        # Hacer todos los campos opcionales excepto nombre y apellido
        self.fields["phone"].required = False
        self.fields["birth_date"].required = False
        self.fields["gender"].required = False

    def clean_phone(self):
        phone = self.cleaned_data.get("phone", "").strip()

        if not phone:
            return None

        # Normalizar
        phone = (
            phone.replace("-", "").replace(" ", "").replace("(", "").replace(")", "")
        )

        if not phone.isdigit():
            raise forms.ValidationError("El teléfono solo debe contener números.")

        if len(phone) != 10:
            raise forms.ValidationError("El teléfono debe tener 10 dígitos.")

        # Verificar unicidad excluyendo el usuario actual
        qs = User.objects.filter(phone=phone)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            raise forms.ValidationError("Este número ya está registrado en el sistema.")

        return phone


class ProfilePhotoForm(forms.Form):
    """
    Formulario para subida de foto de perfil.

    La validación de magic bytes ocurre en ProfileService.upload_profile_photo(),
    aquí solo se valida que se subió un archivo.
    """

    photo = forms.ImageField(
        label="Foto de perfil",
        widget=forms.ClearableFileInput(
            attrs={
                "class": "form-control",
                "accept": "image/jpeg,image/png,image/webp",
            }
        ),
        help_text="JPG, PNG o WEBP. Máximo 5MB.",
    )


class NotificationPreferencesForm(forms.ModelForm):
    """
    Formulario para preferencias de notificación.
    """

    class Meta:
        from accounts.models import NotificationPreferences

        model = NotificationPreferences
        fields = [
            "email_order_updates",
            "email_event_updates",
            "email_team_updates",
        ]
        labels = {
            "email_order_updates": "Notificarme sobre actualizaciones de pedidos",
            "email_event_updates": "Notificarme sobre eventos y competencias",
            "email_team_updates": "Notificarme sobre cambios en mi equipo",
        }
        widgets = {
            "email_order_updates": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "email_event_updates": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "email_team_updates": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
        }


class PrivacySettingsForm(forms.ModelForm):
    """
    Formulario para configuración de privacidad.
    """

    class Meta:
        from accounts.models import PrivacySettings

        model = PrivacySettings
        fields = [
            "profile_visibility",
            "show_photo",
            "show_stats",
            "share_measurements_with_judges",
        ]
        labels = {
            "profile_visibility": "¿Quién puede ver mi perfil?",
            "show_photo": "Mostrar mi foto públicamente",
            "show_stats": "Mostrar mis estadísticas deportivas",
            "share_measurements_with_judges": "Compartir medidas con jueces en eventos",
        }
        widgets = {
            "profile_visibility": forms.Select(attrs={"class": "form-select"}),
            "show_photo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "show_stats": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "share_measurements_with_judges": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
        }

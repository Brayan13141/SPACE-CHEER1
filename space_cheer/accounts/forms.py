from django import forms
from allauth.account.forms import SignupForm
from .models import User, Role
import re
from .models import UserAddress
from django.core.exceptions import ValidationError


# Roles que un usuario puede elegirse a sí mismo durante el onboarding.
# ADMIN, JUEZ, STAFF nunca se auto-asignan — los asigna un admin.
SELF_ASSIGNABLE_ROLES = ["HEADCOACH", "ATHLETE", "GUARDIAN"]


class UserProfilingForm(forms.ModelForm):
    """
    Formulario de onboarding inicial.

    Solo expone roles que un usuario puede elegirse a sí mismo.
    Roles privilegiados (ADMIN, STAFF, JUEZ) los asigna un administrador
    desde el panel de Django o desde coach/views.py.
    """

    role = forms.ModelChoiceField(
        # Filtrar solo roles auto-asignables y que permitan acceso al dashboard
        queryset=Role.objects.filter(
            name__in=SELF_ASSIGNABLE_ROLES,
            allow_dashboard_access=True,
        ).order_by("name"),
        required=True,
        label="¿Cuál es tu rol?",
        empty_label="Selecciona tu rol...",
        # Widget con ayuda visual — el template puede usar esto
        widget=forms.RadioSelect,
    )

    class Meta:
        model = User
        fields = ("first_name", "last_name", "phone", "birth_date", "gender")
        widgets = {
            "birth_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # first_name y last_name son obligatorios en onboarding
        self.fields["first_name"].required = True
        self.fields["last_name"].required = True

        # phone y birth_date opcionales en onboarding (pueden completarse después)
        self.fields["phone"].required = False
        self.fields["birth_date"].required = False
        self.fields["gender"].required = False

    def clean_phone(self):
        phone = self.cleaned_data.get("phone")

        if not phone:
            return phone

        # Normalizar
        phone = (
            phone.strip()
            .replace(" ", "")
            .replace("-", "")
            .replace("(", "")
            .replace(")", "")
        )

        if not phone.isdigit():
            raise ValidationError("El teléfono solo debe contener números.")

        if len(phone) != 10:
            raise ValidationError("El teléfono debe tener exactamente 10 dígitos.")

        # Verificar duplicado excluyendo instancia actual
        qs = User.objects.filter(phone=phone)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            raise ValidationError("Ya existe un usuario con este número de teléfono.")

        return phone

    def clean_birth_date(self):
        """
        Validar que la fecha de nacimiento no sea futura.
        Relevante para detectar menores de edad correctamente.
        """
        from django.utils import timezone

        birth_date = self.cleaned_data.get("birth_date")

        if birth_date and birth_date > timezone.now().date():
            raise ValidationError("La fecha de nacimiento no puede estar en el futuro.")

        return birth_date


class CurpForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("curp",)

    def clean_curp(self):
        curp = self.cleaned_data.get("curp")

        if not curp:
            raise forms.ValidationError("Debes ingresar una CURP.")

        curp = curp.upper()
        regex = r"^[A-Z]{4}\d{6}[HM][A-Z]{5}[A-Z0-9]{2}$"

        if not re.match(regex, curp):
            raise forms.ValidationError("La CURP no tiene un formato válido.")

        return curp


class CustomSignupForm(SignupForm):
    """
    Formulario de registro personalizado con validación de términos
    y validación de email único
    """

    # Definimos el campo explícitamente para que Django lo valide
    terms = forms.BooleanField(
        required=True,  # Esto fuerza la validación en el servidor
        error_messages={
            "required": "Debes aceptar los términos y condiciones para continuar."
        },
        label="Acepto los términos y condiciones",
    )

    def clean_email(self):
        """
        Valida que el email sea único en el sistema
        """
        email = self.cleaned_data.get("email")

        if not email:
            raise ValidationError("El correo electrónico es obligatorio.")

        # Normalizar email (lowercase y trim)
        email = email.lower().strip()

        # Verificar si ya existe
        if User.objects.filter(email=email).exists():
            raise ValidationError(
                "Ya existe un usuario con este correo electrónico. "
                "¿Olvidaste tu contraseña? Usa la opción de recuperación."
            )

        return email

    def save(self, request):
        # 1. Guardamos el usuario base (username, email, password)
        user = super().save(request)

        # 2. Guardamos el booleano en tu modelo personalizado
        # Como el campo 'terms' tiene required=True, si llegamos aquí, es True.
        user.terms_accepted = True
        user.privacy_accepted = True  # Asumimos que el checkbox cubre ambos
        user.save()

        return user


class UserAddressForm(forms.ModelForm):
    class Meta:
        model = UserAddress
        fields = ["label", "address", "city", "zip_code", "is_default"]
        widgets = {
            "label": forms.TextInput(attrs={"class": "form-control"}),
            "address": forms.TextInput(attrs={"class": "form-control"}),
            "city": forms.TextInput(attrs={"class": "form-control"}),
            "zip_code": forms.TextInput(attrs={"class": "form-control"}),
            "is_default": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

from django import forms
from allauth.account.forms import SignupForm
from .models import User, Role
import re
from .models import UserAddress
from django.core.exceptions import ValidationError


class UserProfilingForm(forms.ModelForm):

    role = forms.ModelChoiceField(
        queryset=Role.objects.all(),
        required=True,
        label="Selecciona tu Rol",
        empty_label=None,
    )

    class Meta:
        model = User
        fields = ("first_name", "last_name", "phone", "birth_date", "gender")

        widgets = {
            "birth_date": forms.DateInput(attrs={"type": "date"}),
        }

    def clean_phone(self):
        """
        Valida que el teléfono sea único si se proporciona
        """
        phone = self.cleaned_data.get("phone")

        if not phone:
            return phone

        # Normalizar teléfono (eliminar espacios, guiones, paréntesis)
        phone = (
            phone.strip()
            .replace(" ", "")
            .replace("-", "")
            .replace("(", "")
            .replace(")", "")
        )

        # Validar formato básico (solo números)
        if not phone.isdigit():
            raise ValidationError("El teléfono solo debe contener números.")

        # Validar longitud (10 dígitos para México)
        if len(phone) != 10:
            raise ValidationError("El teléfono debe tener exactamente 10 dígitos.")

        # Verificar si ya existe (excluyendo el usuario actual si es edición)
        queryset = User.objects.filter(phone=phone)
        if self.instance and self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)

        if queryset.exists():
            raise ValidationError(
                "Ya existe un usuario con este número de teléfono. "
                "Por favor, usa otro número o contacta al administrador."
            )

        return phone


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

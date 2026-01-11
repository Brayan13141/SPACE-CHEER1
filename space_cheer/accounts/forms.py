from django import forms
from allauth.account.forms import SignupForm
from .models import User, Role
import re


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
    # Definimos el campo explícitamente para que Django lo valide
    terms = forms.BooleanField(
        required=True,  # Esto fuerza la validación en el servidor
        error_messages={
            "required": "Debes aceptar los términos y condiciones para continuar."
        },
        label="Acepto los términos y condiciones",
    )

    def save(self, request):
        # 1. Guardamos el usuario base (username, email, password)
        user = super().save(request)

        # 2. Guardamos el booleano en tu modelo personalizado
        # Como el campo 'terms' tiene required=True, si llegamos aquí, es True.
        user.terms_accepted = True
        user.privacy_accepted = True  # Asumimos que el checkbox cubre ambos
        user.save()

        return user

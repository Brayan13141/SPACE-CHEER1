# forms.py
from django import forms
from .models import Team, TeamCategory
from django.contrib.auth import get_user_model

User = get_user_model()


class TeamCategoryForm(
    forms.ModelForm
):  # FORMULARIO PARA CREAR/EDITAR CATEGORÍAS DE EQUIPOS
    class Meta:
        model = TeamCategory
        fields = ["name", "level", "description"]

        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "level": forms.NumberInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }


class TeamForm(forms.ModelForm):  # FORMULARIO PARA CREAR/EDITAR EQUIPOS
    def clean_category(self):
        category = self.cleaned_data.get('category')
        # Solo validar al editar un equipo existente que cambia de categoría
        if self.instance.pk and category != self.instance.category:
            from events.models import EventTeamRegistration
            has_active = EventTeamRegistration.objects.filter(
                team=self.instance,
                status__in=[
                    EventTeamRegistration.STATUS_PENDING,
                    EventTeamRegistration.STATUS_ACCEPTED,
                ],
            ).exists()
            if has_active:
                raise forms.ValidationError(
                    'No puedes cambiar la categoría del equipo mientras esté '
                    'inscrito en un evento activo (inscripción pendiente o aceptada).'
                )
        return category
    class Meta:
        model = Team
        fields = ["name", "coach", "address", "city", "phone", "logo", "category"]
        labels = {
            "name": "Nombre del Equipo",
            "coach": "Entrenador Principal",
            "address": "Dirección",
            "city": "Ciudad",
            "phone": "Teléfono",
            "logo": "Logo del Equipo",
            "category": "Categoría",
        }
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "coach": forms.Select(attrs={"class": "form-control"}),
            "address": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "city": forms.TextInput(attrs={"class": "form-control"}),
            "phone": forms.TextInput(attrs={"class": "form-control"}),
            "logo": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "category": forms.Select(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):

        # Recibir request
        self.request = kwargs.pop("request", None)

        super().__init__(*args, **kwargs)

        # Filtrar coaches válidos
        coaches = User.objects.filter(roles__name__in=["COACH", "HEADCOACH"]).distinct()
        self.fields["coach"].queryset = coaches

        # Ordenar categorías
        self.fields["category"].queryset = TeamCategory.objects.all().order_by(
            "level", "name"
        )

        # ---- LÓGICA DE OCULTAR/ASIGNAR COACH ----

        if self.request:

            user = self.request.user

            es_admin = user.is_superuser or user.roles.filter(name="ADMIN").exists()
            es_head = user.roles.filter(name="HEADCOACH").exists()

            # Si es HEADCOACH → ocultar campo y asignarlo a sí mismo
            if es_head and not es_admin:
                self.fields["coach"].initial = user
                self.fields["coach"].widget = forms.HiddenInput()

            # Si es admin o superuser → mostrar el campo
            elif es_admin:
                pass  # no hacemos nada


class QuickAthleteRegisterForm(forms.ModelForm):

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "phone"]

        widgets = {
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "phone": forms.TextInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

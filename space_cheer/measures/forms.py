from django import forms
from .models import MeasurementField, MeasurementValue


# FORMULARIO DINÁMICO PARA MEDIDAS
class DynamicMeasurementsForm(forms.Form):

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        fields = MeasurementField.objects.filter(is_active=True).order_by("order")

        for f in fields:
            existing_value = MeasurementValue.objects.filter(user=user, field=f).first()

            initial = existing_value.value if existing_value else ""

            if f.field_type == "integer":
                self.fields[f.slug] = forms.IntegerField(
                    required=f.required,
                    label=f"{f.name} ({f.unit})" if f.unit else f.name,
                    initial=initial,
                )
            elif f.field_type == "decimal":
                self.fields[f.slug] = forms.DecimalField(
                    required=f.required,
                    label=f"{f.name} ({f.unit})" if f.unit else f.name,
                    initial=initial,
                )
            else:
                self.fields[f.slug] = forms.CharField(
                    required=f.required,
                    label=f.name,
                    initial=initial,
                )


# FORMULARIO PARA CREAR/EDITAR MEDIDAS
class MeasurementFieldForm(forms.ModelForm):

    class Meta:
        model = MeasurementField

        fields = [
            "name",
            "slug",
            "order",
            "field_type",
            "unit",
            "required",
            "is_active",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "slug": forms.TextInput(attrs={"class": "form-control"}),
            "field_type": forms.Select(attrs={"class": "form-control"}),
            "unit": forms.TextInput(attrs={"class": "form-control"}),
            "required": forms.CheckboxInput(),
            "order": forms.NumberInput(attrs={"class": "form-control"}),
        }

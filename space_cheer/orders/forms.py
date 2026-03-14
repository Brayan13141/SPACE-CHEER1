# orders/forms.py
from django import forms
from orders.models import Order


class OrderDatesForm(forms.ModelForm):

    class Meta:
        model = Order
        fields = [
            "freeze_payment_date",
            "measurements_due_date",
            "uniform_delivery_date",
            "first_payment_date",
        ]
        widgets = {
            "freeze_payment_date": forms.DateInput(
                attrs={"type": "date", "class": "form-control"},
                format="%Y-%m-%d",
            ),
            "measurements_due_date": forms.DateInput(
                attrs={"type": "date", "class": "form-control"},
                format="%Y-%m-%d",
            ),
            "uniform_delivery_date": forms.DateInput(
                attrs={"type": "date", "class": "form-control"},
                format="%Y-%m-%d",
            ),
            "first_payment_date": forms.DateInput(
                attrs={"type": "date", "class": "form-control"},
                format="%Y-%m-%d",
            ),
        }
        labels = {
            "freeze_payment_date": "Fecha de pago de congelación",
            "measurements_due_date": "Fecha límite de medidas",
            "uniform_delivery_date": "Fecha de entrega de uniformes",
            "first_payment_date": "Fecha de pago final",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Necesario para que los DateInput rendericen el valor correcto
        for field_name in self.fields:
            self.fields[field_name].required = False

    def clean(self):
        cleaned = super().clean()
        measurements_due = cleaned.get("measurements_due_date")
        uniform_delivery = cleaned.get("uniform_delivery_date")

        if measurements_due and uniform_delivery:
            if uniform_delivery < measurements_due:
                raise forms.ValidationError(
                    "La fecha de entrega de uniformes no puede ser anterior "
                    "a la fecha límite de medidas."
                )

        return cleaned

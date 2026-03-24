from django import forms
from products.models import Product, Season
from products.product_templates import PRODUCT_TEMPLATES
from teams.models import Team


class ProductForm(forms.ModelForm):
    def __init__(self, *args, template_key=None, **kwargs):
        super().__init__(*args, **kwargs)

        # Si viene una plantilla, inicializamos y ocultamos campos obligatorios
        if template_key:
            template = PRODUCT_TEMPLATES.get(template_key, {})
            defaults = template.get("defaults", {})

            for field_name in ["product_type", "usage_type", "size_strategy", "scope"]:
                if field_name in self.fields:
                    self.fields[field_name].widget = forms.HiddenInput()
                    self.fields[field_name].initial = defaults.get(field_name)
                    self.fields[field_name].required = True

    season = forms.ModelChoiceField(
        queryset=Season.objects.filter(is_active=True),
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    owner_team = forms.ModelChoiceField(
        queryset=Team.objects.all(),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
        help_text="Solo requerido si el producto es exclusivo de un equipo",
    )

    class Meta:
        model = Product
        fields = [
            "name",
            "description",
            "product_type",
            "usage_type",
            "size_strategy",
            "scope",
            "owner_team",
            "season",
            "image",
            "base_price",
            "is_active",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "product_type": forms.Select(attrs={"class": "form-select"}),
            "usage_type": forms.Select(attrs={"class": "form-select"}),
            "size_strategy": forms.Select(attrs={"class": "form-select"}),
            "scope": forms.Select(attrs={"class": "form-select"}),
            "season": forms.Select(attrs={"class": "form-select"}),
            "image": forms.ClearableFileInput(
                attrs={"class": "form-control", "accept": "image/*"}
            ),
            "base_price": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01"}
            ),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def clean(self):
        cleaned = super().clean()
        scope = cleaned.get("scope")
        if scope == "CATALOG":
            cleaned["owner_team"] = None
        return cleaned

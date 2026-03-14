from django import forms
from products.models import Product, Season
from teams.models import Team


class ProductForm(forms.ModelForm):
    def __init__(self, *args, template_key=None, **kwargs):
        super().__init__(*args, **kwargs)

        if template_key:
            self.fields["product_type"].disabled = True
            self.fields["usage_type"].disabled = True
            self.fields["scope"].disabled = True
            self.fields["size_strategy"].disabled = True

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
                attrs={
                    "class": "form-control",
                    "accept": "image/*",
                }
            ),
            "base_price": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01"}
            ),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def clean(self):
        cleaned = super().clean()

        scope = cleaned.get("scope")
        # Si es catálogo, forzamos owner_team a None
        if scope == "CATALOG":
            cleaned["owner_team"] = None

        return cleaned

"""Forms de configuración del portal social — 4 tarjetas, una por form."""

from django import forms

from social.models import SocialProfile

_SELECT = {"class": "form-select"}
_CHECK = {"class": "form-check-input"}


class SocialProfileForm(forms.ModelForm):
    class Meta:
        model = SocialProfile
        fields = ["bio", "avatar", "cover"]
        widgets = {
            "bio": forms.Textarea(
                attrs={"class": "form-control", "rows": 3, "maxlength": 300}
            ),
            "avatar": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "cover": forms.ClearableFileInput(attrs={"class": "form-control"}),
        }


class SocialPrivacyForm(forms.ModelForm):
    class Meta:
        model = SocialProfile
        fields = ["profile_visibility", "posts_visibility", "hide_activity"]
        widgets = {
            "profile_visibility": forms.Select(attrs=_SELECT),
            "posts_visibility": forms.Select(attrs=_SELECT),
            "hide_activity": forms.CheckboxInput(attrs=_CHECK),
        }


class SocialNotificationsForm(forms.ModelForm):
    class Meta:
        model = SocialProfile
        fields = ["notify_likes", "notify_comments", "notify_reposts"]
        widgets = {
            "notify_likes": forms.CheckboxInput(attrs=_CHECK),
            "notify_comments": forms.CheckboxInput(attrs=_CHECK),
            "notify_reposts": forms.CheckboxInput(attrs=_CHECK),
        }


class SocialAppearanceForm(forms.ModelForm):
    class Meta:
        model = SocialProfile
        fields = ["feed_density"]
        widgets = {"feed_density": forms.Select(attrs=_SELECT)}

# accounts/adapters/social_adapter.py

from django.shortcuts import redirect
from django.urls import reverse
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from accounts.utils.redirect_flow import get_user_redirect_flow


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):

    def pre_social_login(self, request, sociallogin):
        """
        Conecta automáticamente una cuenta social a un usuario existente con el mismo email,
        previniendo cuentas duplicadas cuando el usuario ya se registró con contraseña.
        """
        if sociallogin.is_existing:
            return

        from django.contrib.auth import get_user_model
        User = get_user_model()

        email = sociallogin.account.extra_data.get("email", "").lower().strip()
        if not email:
            raise ImmediateHttpResponse(redirect(reverse("account_login")))

        try:
            existing_user = User.objects.get(email=email)
            sociallogin.connect(request, existing_user)
        except User.DoesNotExist:
            pass

    def get_login_redirect_url(self, request):
        return get_user_redirect_flow(request.user)

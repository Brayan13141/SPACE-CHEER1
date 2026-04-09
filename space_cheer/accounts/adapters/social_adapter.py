# accounts/adapters/social_adapter.py

from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from accounts.utils.redirect_flow import get_user_redirect_flow


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):

    def get_login_redirect_url(self, request):
        return get_user_redirect_flow(request.user)

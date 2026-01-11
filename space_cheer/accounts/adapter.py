# accounts/adapter.py
from allauth.account.adapter import DefaultAccountAdapter


class CustomAccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request):
        return True

    def get_login_redirect_url(self, request):
        if not request.user.is_superuser:
            return "/dashboard/"

        return "/accounts/complete-profile/"

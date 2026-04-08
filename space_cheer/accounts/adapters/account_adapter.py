# accounts/adapters/account_adapter.py

from allauth.account.adapter import DefaultAccountAdapter
from accounts.utils.redirect_flow import get_user_redirect_flow


class CustomAccountAdapter(DefaultAccountAdapter):

    def is_open_for_signup(self, request):
        return True

    def get_login_redirect_url(self, request):
        if not request.user.profile_completed:
            return get_user_redirect_flow(request.user)

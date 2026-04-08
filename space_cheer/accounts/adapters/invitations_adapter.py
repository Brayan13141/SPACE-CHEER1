# accounts/adapters/invitations_adapter.py

from invitations.adapters import BaseInvitationsAdapter
from allauth.account.signals import user_signed_up


class CustomInvitationsAdapter(BaseInvitationsAdapter):

    def get_user_signed_up_signal(self):
        return user_signed_up

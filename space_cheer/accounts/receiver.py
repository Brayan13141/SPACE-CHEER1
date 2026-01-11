from allauth.account.signals import user_signed_up
from allauth.socialaccount.models import SocialAccount
from django.dispatch import receiver
from allauth.account.models import EmailAddress


@receiver(user_signed_up)
def user_signed_up_receiver(request, user, **kwargs):
    # Si viene de socialaccount, marcar email como verificado
    if SocialAccount.objects.filter(user=user).exists():
        # crea EmailAddress y marca verificado

        EmailAddress.objects.get_or_create(
            user=user, email=user.email, verified=True, primary=True
        )

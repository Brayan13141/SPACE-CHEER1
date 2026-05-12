import logging

from celery import shared_task
from django.contrib.auth import get_user_model
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)
User = get_user_model()


@shared_task(
    bind=True,
    name="accounts.tasks.send_athlete_credentials",
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True,
    acks_late=True,
)
def send_athlete_credentials(self, user_id: int, temp_password: str, login_url: str):
    """
    Envía las credenciales temporales al atleta recién creado.
    Solo corre si el atleta tiene email registrado.
    """
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        logger.error(
            "[TASK] Usuario id=%s no encontrado, no se envía email de credenciales.",
            user_id,
        )
        return

    if not user.email:
        logger.info(
            "[TASK] Usuario id=%s sin email, se omite el envío de credenciales.",
            user_id,
        )
        return

    context = {
        "name": user.get_full_name() or user.username,
        "username": user.username,
        "temp_password": temp_password,
        "login_url": login_url,
    }

    subject = "Tus credenciales de acceso — SPACE CHEER"
    text_body = render_to_string("emails/athlete_credentials.txt", context)
    html_body = render_to_string("emails/athlete_credentials.html", context)

    msg = EmailMultiAlternatives(subject=subject, body=text_body, to=[user.email])
    msg.attach_alternative(html_body, "text/html")
    msg.send()

    logger.info(
        "[TASK] Credenciales enviadas al usuario id=%s (%s).",
        user_id,
        user.email,
    )

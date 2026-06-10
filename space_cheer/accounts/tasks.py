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


@shared_task(
    bind=True,
    name="accounts.tasks.notify_headcoach_approved",
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True,
    acks_late=True,
)
def notify_headcoach_approved(self, user_id: int):
    """Avisa al HEADCOACH que su cuenta fue activada por el admin."""
    from django.urls import reverse

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        logger.error("[TASK] Usuario id=%s no encontrado (headcoach approved).", user_id)
        return

    if not user.email:
        logger.info("[TASK] Usuario id=%s sin email, se omite aviso de aprobación.", user_id)
        return

    context = {
        "name": user.get_full_name() or user.username,
        "login_url": reverse("account_login"),
    }
    subject = "Tu cuenta de entrenador fue aprobada — SPACE CHEER"
    text_body = render_to_string("emails/headcoach_approved.txt", context)
    html_body = render_to_string("emails/headcoach_approved.html", context)
    msg = EmailMultiAlternatives(subject=subject, body=text_body, to=[user.email])
    msg.attach_alternative(html_body, "text/html")
    msg.send()
    logger.info("[TASK] Aviso de aprobación enviado a user id=%s.", user_id)


def _team_recipients(team):
    """Coach dueño + COACHes aceptados del equipo, con email."""
    from teams.models import UserTeamMembership

    recipients = set()
    if team.coach.email:
        recipients.add(team.coach.email)
    coach_memberships = (
        UserTeamMembership.objects.filter(
            team=team, role_in_team="COACH", status="accepted", is_active=True
        ).select_related("user")
    )
    for m in coach_memberships:
        if m.user.email:
            recipients.add(m.user.email)
    return list(recipients)


@shared_task(
    bind=True,
    name="accounts.tasks.notify_team_join_request",
    max_retries=3, default_retry_delay=60,
    autoretry_for=(Exception,), retry_backoff=True, acks_late=True,
)
def notify_team_join_request(self, membership_id: int):
    from teams.models import UserTeamMembership

    try:
        m = UserTeamMembership.objects.select_related("user", "team", "team__coach").get(id=membership_id)
    except UserTeamMembership.DoesNotExist:
        logger.error("[TASK] Membership id=%s no encontrada.", membership_id)
        return

    recipients = _team_recipients(m.team)
    if not recipients:
        return
    context = {
        "coach_name": m.team.coach.get_full_name() or m.team.coach.username,
        "athlete_name": m.user.get_full_name() or m.user.username,
        "team_name": m.team.name,
    }
    subject = f"Nueva solicitud de unión — {m.team.name}"
    text_body = render_to_string("emails/team_join_request.txt", context)
    html_body = render_to_string("emails/team_join_request.html", context)
    msg = EmailMultiAlternatives(subject=subject, body=text_body, to=recipients)
    msg.attach_alternative(html_body, "text/html")
    msg.send()


@shared_task(
    bind=True,
    name="accounts.tasks.notify_join_decision",
    max_retries=3, default_retry_delay=60,
    autoretry_for=(Exception,), retry_backoff=True, acks_late=True,
)
def notify_join_decision(self, membership_id: int, accepted: bool):
    from teams.models import UserTeamMembership

    try:
        m = UserTeamMembership.objects.select_related("user", "team").get(id=membership_id)
    except UserTeamMembership.DoesNotExist:
        logger.error("[TASK] Membership id=%s no encontrada.", membership_id)
        return
    if not m.user.email:
        return
    verb = "aceptada" if accepted else "rechazada"
    context = {
        "athlete_name": m.user.get_full_name() or m.user.username,
        "team_name": m.team.name,
        "verb": verb,
    }
    subject = f"Tu solicitud fue {verb} — {m.team.name}"
    text_body = render_to_string("emails/team_join_decision.txt", context)
    html_body = render_to_string("emails/team_join_decision.html", context)
    msg = EmailMultiAlternatives(subject=subject, body=text_body, to=[m.user.email])
    msg.attach_alternative(html_body, "text/html")
    msg.send()

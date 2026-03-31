from invitations.adapters import BaseInvitationsAdapter
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string


class CustomInvitationsAdapter(BaseInvitationsAdapter):
    def send_mail(self, subject_template, email_template, context, to_email):
        subject = render_to_string(subject_template, context).strip()
        text_body = render_to_string(email_template, context)
        html_body = render_to_string(
            "invitations/email/email_invite_message.html", context
        )

        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            to=[to_email],
        )
        msg.attach_alternative(html_body, "text/html")
        msg.send()

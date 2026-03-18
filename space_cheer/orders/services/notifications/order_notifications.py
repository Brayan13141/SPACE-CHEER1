from django.core.mail import EmailMultiAlternatives
from django.conf import settings


class OrderNotificationService:
    """
    Servicio centralizado para notificaciones de órdenes.
    """

    @staticmethod
    def _send_email(subject, to_emails, text_content, html_content=None):
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=to_emails,
        )

        if html_content:
            email.attach_alternative(html_content, "text/html")

        email.send(fail_silently=False)

    # =====================================================
    # NOTIFICACIONES
    # =====================================================

    @classmethod
    def notify_design_approved(cls, order, triggered_by):
        recipients = cls._get_recipients(order)

        subject = f"Orden #{order.id} - Diseño aprobado 🎨"

        text = f"""
        El diseño de la orden #{order.id} ha sido aprobado.

        Equipo: {order.owner_team or 'N/A'}
        Usuario: {triggered_by}

        Ya puedes continuar con el siguiente paso.
        """

        html = f"""
        <h2>Diseño aprobado 🎨</h2>
        <p>La orden <strong>#{order.id}</strong> ha sido aprobada.</p>
        <p><b>Acción realizada por:</b> {triggered_by}</p>
        """

        cls._send_email(subject, recipients, text, html)

    @classmethod
    def notify_production_started(cls, order, triggered_by):
        recipients = cls._get_recipients(order)

        subject = f"Orden #{order.id} en producción 🏭"

        text = f"""
        La orden #{order.id} ha iniciado producción.
        """

        html = f"""
        <h2>Producción iniciada 🏭</h2>
        <p>La orden <strong>#{order.id}</strong> ya está en producción.</p>
        """

        cls._send_email(subject, recipients, text, html)

    @classmethod
    def notify_order_delivered(cls, order, triggered_by):
        recipients = cls._get_recipients(order)

        subject = f"Orden #{order.id} entregada 📦"

        text = f"""
        La orden #{order.id} ha sido entregada.
        """

        html = f"""
        <h2>Orden entregada 📦</h2>
        <p>La orden <strong>#{order.id}</strong> ha sido entregada con éxito.</p>
        """

        cls._send_email(subject, recipients, text, html)

    # =====================================================
    # HELPERS
    # =====================================================

    @staticmethod
    def _get_recipients(order):
        """
        Define quién recibe notificaciones.
        """
        emails = set()

        if order.owner_user and order.owner_user.email:
            emails.add(order.owner_user.email)

        if order.owner_team:
            members = order.owner_team.memberships.select_related("user").all()
            for m in members:
                if m.user.email:
                    emails.add(m.user.email)

        return list(emails)

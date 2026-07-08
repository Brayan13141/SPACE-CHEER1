from django.core.mail import EmailMultiAlternatives
from django.conf import settings


class OrderNotificationService:
    """
    Servicio centralizado para notificaciones de órdenes.
    """

    @staticmethod
    def _send_email(subject, to_emails, text_content, html_content=None):
        if not to_emails:
            return

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
        if not recipients:
            return

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
        if not recipients:
            return

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
        if not recipients:
            return

        subject = f"Orden #{order.id} entregada 📦"

        text = f"""
        La orden #{order.id} ha sido entregada.
        """

        html = f"""
        <h2>Orden entregada 📦</h2>
        <p>La orden <strong>#{order.id}</strong> ha sido entregada con éxito.</p>
        """

        cls._send_email(subject, recipients, text, html)

    @classmethod
    def notify_production_task_completed(cls, task, recipients):
        if not recipients:
            return

        to_emails = [u.email for u in recipients if u.email]
        if not to_emails:
            return

        product_name = task.order_item.product.name if task.order_item_id else "N/A"
        completed_by = str(task.completed_by) if task.completed_by else "Desconocido"
        notes_text = f"\nNotas: {task.notes}" if task.notes else ""

        subject = f"Orden #{task.job.order_id} — Etapa '{task.stage.name}' completada"

        text = f"""
        La etapa "{task.stage.name}" ha sido completada.

        Orden: #{task.job.order_id}
        Producto: {product_name}
        Completada por: {completed_by}
        Fecha: {task.completed_at}{notes_text}
        """

        html = f"""
        <h2>Etapa completada</h2>
        <p>La etapa <strong>{task.stage.name}</strong> de la orden <strong>#{task.job.order_id}</strong> ha sido completada.</p>
        <ul>
            <li><b>Producto:</b> {product_name}</li>
            <li><b>Completada por:</b> {completed_by}</li>
            <li><b>Fecha:</b> {task.completed_at}</li>
        </ul>
        {f'<p><b>Notas:</b> {task.notes}</p>' if task.notes else ''}
        """

        cls._send_email(subject, to_emails, text, html)

    @classmethod
    def notify_task_assigned(cls, task):
        operario = task.assigned_to
        if not operario or not operario.email:
            return

        order = task.job.order
        subject = f"Nueva tarea asignada: {task.stage.name} — Pedido #{order.id}"

        text = f"""
        Hola {operario.get_full_name() or operario.username},

        Se te ha asignado una nueva tarea de producción:

        Etapa: {task.stage.name}
        Pedido: #{order.id}

        Ingresa al dashboard de producción para ver los detalles y marcarla como completada.
        """

        html = f"""
        <h2>Nueva tarea asignada</h2>
        <p>Hola <strong>{operario.get_full_name() or operario.username}</strong>,</p>
        <p>Se te ha asignado una nueva tarea de producción:</p>
        <ul>
            <li><b>Etapa:</b> {task.stage.name}</li>
            <li><b>Pedido:</b> #{order.id}</li>
        </ul>
        <p>Ingresa al dashboard de producción para ver los detalles y marcarla como completada.</p>
        """

        cls._send_email(subject, [operario.email], text, html)

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

        if order.order_type == "OFFLINE" and order.customer and order.customer.user:
            if order.customer.user.email:
                emails.add(order.customer.user.email)

        return list(emails)

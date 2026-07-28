class ManagementNotificationService:
    """Notificaciones de 'gestión' (asignación de tarea, job listo, error
    reportado, etc.) — todo lo que no es notification_type SOCIAL_*, que ya
    tiene su propia campana/lista en social.notification_services."""

    @staticmethod
    def management_qs(user):
        return user.notifications.exclude(notification_type__startswith="SOCIAL_")

    @staticmethod
    def mark_read(user, pk):
        from django.shortcuts import get_object_or_404

        notification = get_object_or_404(
            ManagementNotificationService.management_qs(user), pk=pk
        )
        notification.read = True
        notification.save(update_fields=["read"])
        return notification

    @staticmethod
    def mark_all_read(user):
        return (
            ManagementNotificationService.management_qs(user)
            .filter(read=False)
            .update(read=True)
        )

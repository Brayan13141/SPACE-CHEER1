def social_bell(request):
    """Últimas 10 no leídas para el dropdown — solo en rutas del portal social."""
    if not request.user.is_authenticated or not request.path.startswith("/social/"):
        return {}
    from social.notification_services import SocialNotificationService

    return {"social_bell_items": SocialNotificationService.unread_for(request.user)}

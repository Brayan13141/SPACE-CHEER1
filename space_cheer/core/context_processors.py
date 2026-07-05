from core.help_registry import get_help_cards


def page_help(request):
    view_name = None
    if request.resolver_match:
        view_name = getattr(request.resolver_match, "view_name", None)
    cards = get_help_cards(view_name, request.user) if view_name else []
    return {
        "page_help_cards": cards,                      # list[str] para el carousel del modal
        "page_help_text": cards[0] if cards else "",   # compat con los ⓘ inline existentes
    }


def feature_flags(request):
    """Expone flags de features a todos los templates."""
    from django.conf import settings

    return {"preview_3d_enabled": settings.PREVIEW_3D_ENABLED}

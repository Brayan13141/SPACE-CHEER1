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

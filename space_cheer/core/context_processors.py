from core.help_registry import get_help_text


def page_help(request):
    view_name = None
    if request.resolver_match:
        view_name = getattr(request.resolver_match, "view_name", None)
    text = get_help_text(view_name, request.user) if view_name else ""
    return {"page_help_text": text}

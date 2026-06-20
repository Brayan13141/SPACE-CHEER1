from django import template
from django.utils.html import format_html

register = template.Library()


@register.simple_tag
def help_icon(text, placement="top"):
    return format_html(
        '<button type="button" class="btn btn-link p-0 ms-1 sc-help-icon"'
        ' data-bs-toggle="popover" data-bs-placement="{}"'
        ' data-bs-trigger="hover focus" data-bs-content="{}"'
        ' aria-label="Más información">'
        '<i class="bi bi-info-circle text-info"></i></button>',
        placement,
        text,
    )

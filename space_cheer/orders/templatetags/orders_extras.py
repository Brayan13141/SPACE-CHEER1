"""Template tags/filters auxiliares para plantillas de orders."""
from django import template

register = template.Library()


@register.filter
def dict_get(dictionary, key):
    """Devuelve dictionary.get(key, "") de forma segura.

    Django templates no soportan lookup dinamico de claves (p.ej.
    `mydict[variable]`), por lo que este filtro permite hacer
    `{{ mydict|dict_get:variable }}` en su lugar. Tolera que
    `dictionary` sea None o cualquier valor que no sea un dict.
    """
    if not isinstance(dictionary, dict):
        return ""
    return dictionary.get(key, "")

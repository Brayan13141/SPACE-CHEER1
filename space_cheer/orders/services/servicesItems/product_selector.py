from products.models import Product
from django.db.models import Q


def available_products_for_order(order):
    """
    Devuelve los productos disponibles según el tipo de orden y su contexto
    """

    base_qs = Product.objects.filter(
        season__is_active=True,
    )

    # -------------------------
    # Filtrado por scope
    # -------------------------
    if order.order_type == "TEAM":
        base_qs = base_qs.filter(
            Q(scope="CATALOG") | Q(scope="TEAM_ONLY", owner_team=order.owner_team)
        )
    else:
        # Órdenes personales solo pueden usar catálogo
        base_qs = base_qs.filter(scope="CATALOG")

    # -------------------------
    # Filtrado por usage_type
    # -------------------------
    if order.order_type == "PERSONAL":
        # En personal, solo productos que puedan asignarse a una persona
        base_qs = base_qs.filter(usage_type__in=["GLOBAL", "ATHLETE_CUSTOM"])

    elif order.order_type == "TEAM":
        # En equipo, todo menos los exclusivos por atleta
        base_qs = base_qs.filter(
            usage_type__in=["GLOBAL", "TEAM_CUSTOM", "ATHLETE_CUSTOM"]
        )

    return base_qs.order_by("name")

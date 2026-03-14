from decimal import Decimal, InvalidOperation
from django.http import QueryDict
from orders.services.servicesItems.product_selector import available_products_for_order
from typing import Union


class ProductFilterService:
    """
    Aplica filtros dinámicos a los productos disponibles para una orden.
    """

    @staticmethod
    def filter_for_order(*, order, filters: Union[QueryDict, dict]):
        """
        filters puede venir directo de request.GET

        keys soportadas:
        - product_type: list[str]
        - usage_type: list[str]
        - season: str (id)
        - min_price: str | decimal
        - max_price: str | decimal
        - active_only: "on" | None
        """
        if isinstance(filters, dict):
            qd = QueryDict(mutable=True)
            for k, v in filters.items():
                if isinstance(v, list):
                    qd.setlist(k, v)
                else:
                    qd[k] = v
            filters = qd

        qs = available_products_for_order(order)

        # -------------------------
        # Normalización
        # -------------------------
        product_type = [v for v in filters.getlist("product_type") if v]
        usage_type = [v for v in filters.getlist("usage_type") if v]
        season_id = filters.get("season")

        min_price = filters.get("min_price")
        if min_price:
            try:
                qs = qs.filter(base_price__gte=Decimal(min_price))
            except (InvalidOperation, ValueError):
                pass  # o lanzar ValidationError

        max_price = filters.get("max_price")
        if max_price:
            try:
                qs = qs.filter(base_price__lte=Decimal(max_price))
            except (InvalidOperation, ValueError):
                pass  # o lanzar ValidationError

        active_only = filters.get("active_only")

        # -------------------------
        # Aplicación de filtros
        # -------------------------
        if product_type:
            qs = qs.filter(product_type__in=product_type)

        if usage_type:
            qs = qs.filter(usage_type__in=usage_type)

        if season_id:
            qs = qs.filter(season_id=season_id)

        # Default: solo activos
        if active_only is None or active_only == "on":
            qs = qs.filter(is_active=True)

        return qs

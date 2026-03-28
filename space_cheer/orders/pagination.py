"""
Paginación consistente para el módulo de órdenes.
"""

from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from typing import Tuple, Any


class OrderPaginator:
    """Paginador con configuración consistente"""

    DEFAULT_PAGE_SIZE = 25
    MAX_PAGE_SIZE = 100

    @classmethod
    def paginate(
        cls, queryset, page_number: int, page_size: int = None
    ) -> Tuple[Any, dict]:
        """
        Pagina un queryset y retorna el objeto de página + metadata.

        Args:
            queryset: QuerySet a paginar
            page_number: Número de página solicitada
            page_size: Tamaño de página (default: 25)

        Returns:
            Tuple de (page_obj, pagination_info)
        """
        if page_size is None:
            page_size = cls.DEFAULT_PAGE_SIZE

        # Limitar tamaño de página
        page_size = min(page_size, cls.MAX_PAGE_SIZE)

        paginator = Paginator(queryset, page_size)

        try:
            page_obj = paginator.page(page_number)
        except PageNotAnInteger:
            # Si no es entero, dar primera página
            page_obj = paginator.page(1)
        except EmptyPage:
            # Si está fuera de rango, dar última página
            page_obj = paginator.page(paginator.num_pages)

        # Metadata útil para templates
        pagination_info = {
            "total_items": paginator.count,
            "total_pages": paginator.num_pages,
            "current_page": page_obj.number,
            "has_previous": page_obj.has_previous(),
            "has_next": page_obj.has_next(),
            "previous_page": (
                page_obj.previous_page_number() if page_obj.has_previous() else None
            ),
            "next_page": page_obj.next_page_number() if page_obj.has_next() else None,
            "page_range": cls._get_page_range(page_obj.number, paginator.num_pages),
            "start_index": page_obj.start_index(),
            "end_index": page_obj.end_index(),
        }

        return page_obj, pagination_info

    @staticmethod
    def _get_page_range(current_page: int, total_pages: int, window: int = 5) -> list:
        """
        Genera un rango de páginas para mostrar en la navegación.

        Ejemplo: Si estás en página 10 de 100, muestra [8, 9, 10, 11, 12]
        """
        half_window = window // 2

        if total_pages <= window:
            return list(range(1, total_pages + 1))

        # Calcular inicio y fin del rango
        start = max(1, current_page - half_window)
        end = min(total_pages, current_page + half_window)

        # Ajustar si estamos cerca del inicio o fin
        if current_page <= half_window:
            end = min(window, total_pages)
        elif current_page >= total_pages - half_window:
            start = max(1, total_pages - window + 1)

        return list(range(start, end + 1))

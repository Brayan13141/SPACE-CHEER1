"""Hoja imprimible de tallas para el taller.

La pantalla de tallas del pedido es para capturar; esta es para producir: sale
en papel, sin navegacion ni fondos oscuros, con el corte arriba y el reparto
abajo.
"""

from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, render

from accounts.decorators import role_required
from accounts.services.pii_audit_service import PiiAuditService
from orders.models import Order, OrderItemAthlete
from orders.services.sizes.SizeSummaryService import SizeSummaryService


@role_required("ADMIN", "OPERARIO")
def order_sizes_print(request, order_id):
    order = get_object_or_404(
        Order.objects.select_related("owner_team"), pk=order_id
    )

    grupos = SizeSummaryService.for_order(order)
    if not grupos:
        # Un pedido sin productos por talla no tiene hoja que imprimir. 404 y
        # no una hoja en blanco, que en el taller parece un pedido sin tallas.
        raise PermissionDenied(
            "Este pedido no tiene productos con talla por alumno"
        )

    # Se auditan los sujetos que la hoja IMPRIME, que es justo lo que sale del
    # sistema en papel. Las otras pantallas de talla ya registran VIEW_SIZE;
    # sin esto, la unica que se lleva los nombres al taller no dejaria rastro.
    item_ids = [item_id for grupo in grupos for item_id in grupo.item_ids]
    atletas = [
        oia.athlete
        for oia in OrderItemAthlete.objects.filter(
            order_item_id__in=item_ids
        ).select_related("athlete")
    ]
    PiiAuditService.log_many(
        request=request,
        target_users=atletas,
        access_type="VIEW_SIZE",
        field_accessed="standard_size",
        notes=f"Hoja de produccion, Order pk={order_id}",
    )

    return render(
        request,
        "production/order_sizes_print.html",
        {"order": order, "size_groups": grupos},
    )

"""Hoja imprimible de tallas para el taller.

La pantalla de tallas del pedido es para capturar; esta es para producir: sale
en papel, sin navegacion ni fondos oscuros, con el corte arriba y el reparto
abajo.
"""

from django.contrib.auth import get_user_model
from django.http import Http404
from django.shortcuts import get_object_or_404, render

from accounts.decorators import role_required
from accounts.services.pii_audit_service import PiiAuditService
from orders.models import Order
from orders.services.sizes.SizeSummaryService import SizeSummaryService
from production.models import ProductionJob


def _visible_orders(user):
    """El operario solo ve los pedidos en los que tiene trabajo.

    La hoja se lleva al taller nombre y talla de menores, asi que el alcance es
    el mismo que el de las otras pantallas de operario (order_design filtra por
    tasks__assigned_to, item_measurements por production_tasks__assigned_to).
    Sin esto, cualquier operario recorre /pedido/<n>/ y saca el roster completo
    de todos los equipos.
    """
    if user.is_superuser or user.roles.filter(name="ADMIN").exists():
        return Order.objects.all()

    con_trabajo = ProductionJob.objects.filter(
        tasks__assigned_to=user
    ).values_list("order_id", flat=True)
    return Order.objects.filter(pk__in=con_trabajo)


@role_required("ADMIN", "OPERARIO")
def order_sizes_print(request, order_id):
    order = get_object_or_404(
        _visible_orders(request.user).select_related("owner_team"),
        pk=order_id,
    )

    grupos = SizeSummaryService.for_order(order)
    if not grupos:
        # 404 y no una hoja en blanco, que en el taller parece un pedido sin
        # tallas. Tampoco 403: no es un problema de permisos y el boton del
        # panel es incondicional, asi que se llega aca a menudo y sin culpa.
        raise Http404("Este pedido no tiene productos con talla por alumno")

    # Se auditan los sujetos que la hoja IMPRIME, que es lo que sale del
    # sistema en papel: los que tienen talla Y los que salen marcados SIN
    # TALLA, que tambien van con nombre y apellido.
    ids = {
        user_id for grupo in grupos for user_id in grupo.printed_user_ids
    }
    atletas = list(get_user_model().objects.filter(id__in=ids))
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

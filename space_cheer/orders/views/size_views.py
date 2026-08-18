from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import User
from accounts.services.pii_audit_service import PiiAuditService
from orders.models import Order
from orders.services.servicesItems.size_assignment_service import (
    OrderItemSizeAssignmentService,
)
from orders.services.sizes.SizeGridService import SizeGridService
from products.models import Product


@login_required
def order_product_sizes_grid(request, order_id, product_id):
    """Roster de tallas de un producto dentro de una orden.

    Se indexa por (orden, producto) y no por item porque mover a un alumno de M
    a L cruza DOS OrderItem: una pantalla atada a un item no podria
    representar la operacion central de esta feature.
    """
    order = get_object_or_404(Order, pk=order_id)
    product = get_object_or_404(Product, pk=product_id)

    if request.method == "POST":
        grid = SizeGridService.build(order, product, request.user)

        if grid.is_locked or not grid.can_edit:
            # SizeGridService.build ya construyo el grid completo (incluidas
            # las tallas ya asignadas), asi que llamar a reconcile() aqui
            # seria doblemente inutil: assignments_from_post devolveria {}
            # porque ninguna fila es editable, y si igual se llamara,
            # reconcile() lanzaria ValidationError("La orden no es editable")
            # sin que nada la atrape (500 en vez del aviso que pide el diseño).
            messages.error(
                request,
                SizeGridService.LOCKED_MESSAGE
                if grid.is_locked
                else SizeGridService.NO_WRITE_MESSAGE,
            )
            _log_size_view(request, grid, order, product)
            return render(request, "orders/items/sizes_grid.html", {"grid": grid})

        assignments = SizeGridService.assignments_from_post(grid, request.POST)
        result = OrderItemSizeAssignmentService.reconcile(
            order, product, assignments, viewer=request.user
        )

        _log_size_edit(request, order, product, result)

        if result.ok:
            messages.success(request, "Tallas guardadas correctamente.")
            return redirect(
                "orders:order_product_sizes_grid",
                order_id=order.id,
                product_id=product.id,
            )

        messages.error(request, "Revisa las filas marcadas.")
        grid = SizeGridService.build(
            order, product, request.user,
            values=request.POST, errors=result.errors,
        )
        # Un guardado fallido re-renderiza el roster COMPLETO: se ven las
        # tallas igual que en un GET, asi que se audita igual.
        _log_size_view(request, grid, order, product)
        return render(request, "orders/items/sizes_grid.html", {"grid": grid})

    grid = SizeGridService.build(order, product, request.user)
    _log_size_view(request, grid, order, product)
    return render(request, "orders/items/sizes_grid.html", {"grid": grid})


def _log_size_view(request, grid, order, product):
    PiiAuditService.log_many(
        request=request,
        target_users=[row.athlete for row in grid.rows],
        access_type="VIEW_SIZE",
        field_accessed="standard_size",
        notes=f"Grid de tallas orden={order.pk} producto={product.pk}",
    )


def _log_size_edit(request, order, product, result):
    """Audita a los alumnos TOCADOS, que no son solo los que se movieron de fila.

    reconcile() tambien reescribe la talla guardada del alumno (Decision 5), y
    eso pasa incluso cuando el pedido no cambia: si el perfil se corrigio por la
    pantalla del atleta y despues alguien reguarda el roster, la talla del menor
    se revierte. Auditar solo changed_athletes dejaba esa escritura sin rastro.
    """
    tocados = {athlete.id: athlete for athlete in result.changed_athletes}

    faltantes = set(result.profile_updates) - set(tocados)
    if faltantes:
        for athlete in User.objects.filter(id__in=faltantes):
            tocados[athlete.id] = athlete

    for athlete in tocados.values():
        PiiAuditService.log(
            request=request,
            target_user=athlete,
            access_type="EDIT_SIZE",
            field_accessed="standard_size",
            notes=f"Grid de tallas orden={order.pk} producto={product.pk}",
        )

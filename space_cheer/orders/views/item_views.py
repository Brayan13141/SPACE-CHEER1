from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages

from django.core.exceptions import PermissionDenied, ValidationError
from django.contrib.auth.decorators import login_required
from orders.models import OrderItem, Order, OrderItemAthlete
from orders.services.servicesItems.order_item_athlete_service import (
    OrderItemAthleteService,
)
from teams.models import UserTeamMembership
from django.views.decorators.http import require_POST
from products.models import ProductMeasurementField


# ---------------------------------------------------------
# Order Items
# ---------------------------------------------------------
@login_required
def order_item_detail(request, item_id):

    item = get_object_or_404(
        OrderItem.objects.select_related(
            "order", "product", "product__owner_team", "product__season"
        ).filter(order__in=Order.objects.visible_for_user(request.user)),
        id=item_id,
    )

    product = item.product
    order = item.order

    # -------------------------------------------------
    # REGLAS DE CONFIGURACIÓN
    # -------------------------------------------------
    requires_team = product.requires_team
    requires_athlete = product.requires_athletes
    requires_sizes = product.size_strategy == "STANDARD"
    requires_measurements = product.requires_measurements

    # -------------------------------------------------
    # ATLETAS DEL ITEM
    # -------------------------------------------------
    athlete_items = []

    if requires_athlete:
        athlete_items = (
            OrderItemAthlete.objects.filter(order_item=item)
            .select_related("athlete")
            .prefetch_related("measurements", "customization")
        )

    # -------------------------------------------------
    # MEDIDAS REQUERIDAS
    # -------------------------------------------------
    measurement_fields = []

    if requires_measurements:
        measurement_fields = ProductMeasurementField.objects.filter(
            product=product
        ).select_related("field")

    # -------------------------------------------------
    # ESTADO DE CONFIGURACIÓN
    # -------------------------------------------------
    missing_configuration = []

    if requires_athlete and not athlete_items:
        missing_configuration.append("Debe asignar atletas")

    if requires_measurements and not measurement_fields:
        missing_configuration.append("No hay campos de medida configurados")

    configuration_state = "READY" if not missing_configuration else "INCOMPLETE"

    # -------------------------------------------------
    # PERMISOS UI — ahora con lógica real
    # -------------------------------------------------
    can_import_athletes = (
        requires_team
        and requires_athlete
        and order.can_edit_general()  # ← solo si la orden es editable
    )

    can_manage_athletes = (
        requires_athlete and order.can_edit_general()  # ← solo si la orden es editable
    )

    # lógica para eliminar item
    can_delete_item = _can_user_delete_item(request.user, order, item)

    context = {
        "order": order,
        "item": item,
        "product": product,
        "athlete_items": athlete_items,
        "measurement_fields": measurement_fields,
        "requires_athlete": requires_athlete,
        "requires_team": requires_team,
        "requires_sizes": requires_sizes,
        "requires_measurements": requires_measurements,
        "configuration_state": configuration_state,
        "missing_configuration": missing_configuration,
        "can_import_athletes": can_import_athletes,
        "can_manage_athletes": can_manage_athletes,
        "can_delete_item": can_delete_item,
    }

    return render(request, "orders/items/item_detail.html", context)


# -------------------------------------------------
# Helper privado — separado de la view para testear
# -------------------------------------------------


def _can_user_delete_item(user, order, item) -> bool:
    """
    Reglas para eliminar un item de una orden:
    1. La orden debe estar en DRAFT (no enviada)
    2. El usuario debe ser el creador de la orden o staff
    """
    if not order.can_edit_general():
        return False

    if user.is_staff or user.is_superuser:
        return True

    # El creador de la orden puede eliminar sus items
    if order.created_by == user:
        return True

    return False


@login_required
@require_POST
def order_item_delete(request, item_id):
    """
    Elimina un item de una orden.
    Solo permitido si la orden está en DRAFT y el usuario tiene permisos.
    """
    item = get_object_or_404(
        OrderItem.objects.select_related("order", "product"),
        pk=item_id,
        order__in=Order.objects.visible_for_user(request.user),
    )

    order = item.order

    # Verificación de seguridad en el servidor — nunca confíes solo en el template
    if not _can_user_delete_item(request.user, order, item):
        raise PermissionDenied("No tienes permiso para eliminar este producto.")

    product_name = item.product.name
    item.delete()
    order.invalidate_cache()

    messages.success(request, f'Producto "{product_name}" eliminado de la orden.')
    return redirect("orders:detail_order", order_id=order.id)


# --------------------------------------------------------
# Athletes
# ---------------------------------------------------------
# ---------------------------------------------------------


@login_required
@require_POST
def import_team_athletes(request, item_id):

    item = get_object_or_404(
        OrderItem.objects.select_related(
            "order",
            "product",
            "order__owner_team",
        ).prefetch_related(
            "product__measurement_fields__field",
            "athletes__measurements",
        ),
        pk=item_id,
        order__in=Order.objects.visible_for_user(request.user),
    )

    try:
        result = OrderItemAthleteService.import_from_team(item)

        # -------------------------
        # MENSAJES
        # -------------------------
        for err in result["errors"]:
            messages.warning(request, err)

        if result["created"] or result["updated"]:
            messages.success(
                request,
                f'{result["created"]} atletas creados, {result["updated"]} actualizados correctamente.',
            )
        else:
            messages.info(request, "No había cambios para aplicar.")

    except ValidationError as e:
        messages.error(request, e.message)

    return redirect("orders:order_item_detail", item_id=item.id)

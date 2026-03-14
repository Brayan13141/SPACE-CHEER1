from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages

from django.core.exceptions import ValidationError
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
    # REGLAS DE CONFIGURACIÓN DEL PRODUCTO
    # -------------------------------------------------

    requires_team = product.usage_type == "TEAM_CUSTOM"

    requires_athlete = (
        product.usage_type == "ATHLETE_CUSTOM"
        or product.size_strategy == "MEASUREMENTS"
    )

    requires_sizes = product.size_strategy == "STANDARD"

    requires_measurements = product.size_strategy == "MEASUREMENTS"

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
    # PERMISOS UI
    # -------------------------------------------------

    can_import_athletes = requires_team and requires_athlete
    can_manage_athletes = requires_athlete
    can_delete_item = True

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

    return render(
        request,
        "orders/items/item_detail.html",
        context,
    )


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
        ),
        pk=item_id,
        order__in=Order.objects.visible_for_user(request.user),
    )

    order = item.order
    product = item.product

    # -------------------------------------------------
    # VALIDACIONES
    # -------------------------------------------------

    if not order.can_edit_general():
        messages.error(request, "La orden no es editable.")
        return redirect("orders:order_item_detail", item_id=item.id)

    if order.order_type != "TEAM":
        messages.error(request, "Solo órdenes TEAM permiten importar atletas.")
        return redirect("orders:order_item_detail", item_id=item.id)

    if not product.requires_athletes:
        messages.error(request, "Este producto no utiliza atletas.")
        return redirect("orders:order_item_detail", item_id=item.id)

    if not order.owner_team:
        messages.error(request, "La orden no tiene equipo asignado.")
        return redirect("orders:order_item_detail", item_id=item.id)
    if not product.requires_team:
        messages.error(request, "Este producto no pertenece a un equipo.")
        return redirect("orders:order_item_detail", item_id=item.id)

    # -------------------------------------------------
    # OBTENER ATLETAS DEL EQUIPO
    # -------------------------------------------------

    memberships = UserTeamMembership.objects.filter(
        team=order.owner_team,
        status="accepted",
        is_active=True,
        role_in_team="ATLETA",
    ).select_related("user")

    # atletas ya agregados
    existing_ids = set(item.athletes.values_list("athlete_id", flat=True))

    created = 0

    errors = []

    for membership in memberships:
        athlete = membership.user
        if athlete.id in existing_ids:
            continue
        try:
            OrderItemAthleteService.add_athlete(order_item=item, athlete=athlete)
            created += 1
        except ValidationError as e:
            errors.append(f"{athlete}: {', '.join(e.messages)}")

    if errors:
        for err in errors:
            messages.warning(request, err)

    if created:
        messages.success(request, f"{created} atletas importados correctamente.")
    elif not errors:
        messages.info(request, "No había atletas nuevos para importar.")

    return redirect("orders:order_item_detail", item_id=item.id)

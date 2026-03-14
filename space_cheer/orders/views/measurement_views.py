from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from orders.models import Order, OrderItemAthlete
from django.db import transaction


@login_required
@require_POST
def item_measurements_order_add(request, athlete_item_id):

    athlete_item = get_object_or_404(
        OrderItemAthlete.objects.select_related(
            "order_item__order",
            "order_item__product",
        ),
        pk=athlete_item_id,
        order_item__order__created_by=request.user,
    )

    order = athlete_item.order_item.order
    product = athlete_item.order_item.product

    if not order.can_edit_general():
        messages.error(request, "La orden no permite modificar medidas.")
        return redirect(
            "orders:order_item_detail",
            item_id=athlete_item.order_item.id,
        )

    product_fields = product.measurement_fields.select_related("field")

    existing_measurements = {m.field_id: m for m in athlete_item.measurements.all()}

    # ── Paso 1: validar todo ANTES de tocar la DB ───────────────────
    values = {}

    for pmf in product_fields:
        field = pmf.field
        value = request.POST.get(f"field_{field.id}", "").strip()

        if pmf.required and not value:
            messages.error(request, f"El campo '{field.name}' es obligatorio.")
            return redirect(
                "orders:order_item_measurements",
                athlete_item_id=athlete_item_id,
            )

        values[field.id] = (pmf, field, value)

    # ── Paso 2: guardar todo o nada ─────────────────────────────────
    with transaction.atomic():
        for field_id, (pmf, field, value) in values.items():
            measurement = existing_measurements.get(field_id)

            if measurement:
                measurement.value = value
                measurement.save()
            else:
                athlete_item.measurements.create(
                    field_id=field_id,
                    field_name=field.name,
                    field_unit=field.unit,
                    value=value,
                )

    messages.success(request, "Medidas guardadas correctamente.")

    return redirect(
        "orders:order_item_detail",
        item_id=athlete_item.order_item.id,
    )


@login_required
def order_item_measurements(request, athlete_item_id):

    athlete_item = get_object_or_404(
        OrderItemAthlete.objects.select_related(
            "order_item__order",
            "order_item__product",
            "athlete",
        ).prefetch_related(
            "measurements__field",
            "order_item__product__measurement_fields__field",
        ),
        pk=athlete_item_id,
        order_item__order__in=Order.objects.visible_for_user(request.user),
    )

    order = athlete_item.order_item.order
    product = athlete_item.order_item.product

    if not product.requires_measurements:
        messages.error(request, "Este producto no requiere medidas.")
        return redirect(
            "orders:order_item_detail",
            item_id=athlete_item.order_item.id,
        )

    can_edit = order.can_edit_general() and order.can_edit_measurements()

    product_fields = list(product.measurement_fields.select_related("field"))

    # ── Una sola query, construida antes del loop ───────────────────
    existing = {m.field_id: m.value for m in athlete_item.measurements.all()}

    for pf in product_fields:
        pf.current_value = existing.get(pf.field_id, "")

    filled_count = sum(1 for pf in product_fields if existing.get(pf.field_id))

    return render(
        request,
        "orders/items/item_measurements.html",
        {
            "athlete_item": athlete_item,
            "product_fields": product_fields,
            "filled_count": filled_count,
            "total_fields": len(product_fields),
            "can_edit": can_edit,
        },
    )

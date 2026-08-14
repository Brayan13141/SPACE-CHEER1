import logging

from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.core.exceptions import ValidationError, PermissionDenied
from accounts.decorators import role_required
from accounts.models import AthleteProfile
from accounts.services.pii_audit_service import PiiAuditService
from orders.models import Order, OrderItem, OrderItemAthlete
from django.db import transaction
from orders.services.measurements.MeasurementLifecycleService import (
    MeasurementLifecycleService,
)
from orders.services.measurements.MeasurementGridService import (
    MeasurementGridService,
)

logger = logging.getLogger(__name__)


@login_required
def order_item_measurements(request, athlete_item_id):

    athlete_item = get_object_or_404(
        OrderItemAthlete.objects.select_related(
            "order_item__order",
            "order_item__product",
            "athlete",
            "athlete__athleteprofile",
            "athlete__athleteprofile__guardian",
        ).prefetch_related(
            "measurements__field",
            "order_item__product__measurement_fields__field",
        ),
        pk=athlete_item_id,
    )

    order = athlete_item.order_item.order
    user = request.user

    is_authorized = Order.objects.visible_for_user(user).filter(pk=order.pk).exists()
    is_guardian = False
    try:
        profile = athlete_item.athlete.athleteprofile
        if profile.guardian == user and athlete_item.athlete.is_minor:
            is_guardian = True
    except AthleteProfile.DoesNotExist:
        pass

    if not is_authorized and not is_guardian:
        raise PermissionDenied

    PiiAuditService.log(
        request=request,
        target_user=athlete_item.athlete,
        access_type="VIEW_MEASUREMENTS",
        field_accessed="measurements",
        notes=f"OrderItemAthlete pk={athlete_item.pk}",
    )

    product = athlete_item.order_item.product

    if not product.requires_measurements:
        messages.error(request, "Este producto no requiere medidas.")
        return redirect(
            "orders:order_item_detail",
            item_id=athlete_item.order_item.id,
        )

    # Esta pagina se titula "Medidas de <atleta>": el grid se restringe a esa
    # fila. Sin el filtro renderizaba a todo el equipo mientras el log de PII
    # de arriba registraba un solo sujeto.
    grid = MeasurementGridService.build(
        athlete_item.order_item,
        request.user,
        only_athlete_item_id=athlete_item.id,
    )

    return render(
        request,
        "orders/items/item_measurements.html",
        {
            "athlete_item": athlete_item,
            "grid": grid,
            "can_view_item_detail": _can_view_item_detail(
                request, athlete_item.order_item
            ),
        },
    )


@role_required("ADMIN")
@require_POST
def close_measurements(request, order_id):
    order = get_object_or_404(Order, pk=order_id)

    try:
        MeasurementLifecycleService.close(order, user=request.user)
        messages.success(request, "Medidas cerradas correctamente")
    except ValidationError as e:
        messages.error(request, e.message if hasattr(e, 'message') else str(e))
    except Exception as e:
        logger.exception("Error inesperado al cerrar medidas order=%s: %s", order_id, e)
        messages.error(request, "Error interno al cerrar medidas. Contacta al soporte.")

    return redirect("orders:admin_order_detail", order_id=order.id)


@role_required("ADMIN")
@require_POST
def reopen_measurements(request, order_id):
    order = get_object_or_404(Order, pk=order_id)

    try:
        MeasurementLifecycleService.reopen(order, user=request.user)
        messages.success(request, "Medidas reabiertas correctamente")
    except ValidationError as e:
        messages.error(request, e.message if hasattr(e, 'message') else str(e))
    except Exception as e:
        logger.exception("Error inesperado al reabrir medidas order=%s: %s", order_id, e)
        messages.error(request, "Error interno al reabrir medidas. Contacta al soporte.")

    return redirect("orders:admin_order_detail", order_id=order.id)


def _log_grid_view(request, grid, item):
    """Audita a los sujetos que el grid realmente muestra.

    Se llama en TODA rama que renderiza el grid (GET y POST fallido). En el
    flujo normal -- abrir la pagina y luego guardar -- el GET ya registro a
    todos y log_many coalesce el re-render dentro de su ventana: el acceso
    queda asentado una vez, no dos. Lo que esto cierra es el POST que falla
    SIN GET previo (envio directo, o vuelta despues de que expiro la ventana),
    donde antes se renderizaba el roster completo sin dejar ningun rastro.
    """
    PiiAuditService.log_many(
        request=request,
        target_users=[row.athlete for row in grid.rows],
        access_type="VIEW_MEASUREMENTS",
        field_accessed="measurements",
        notes=f"Grid OrderItem pk={item.pk}",
    )


def _can_view_item_detail(request, item):
    """El guardian puede abrir el grid pero NO order_item_detail.

    order_item_detail filtra por Order.objects.visible_for_user(), que no
    contempla guardianes; ofrecerle el enlace seria mandarlo a un 404.
    """
    return (
        Order.objects.visible_for_user(request.user)
        .filter(pk=item.order_id)
        .exists()
    )


@login_required
def item_measurements_grid(request, item_id):
    """Tabla consolidada de medidas del item: filas = alumnos, columnas = campos.

    GET  -> pagina de captura.
    POST -> guarda; si hay errores, re-renderiza conservando lo tecleado.
    """
    item = get_object_or_404(
        OrderItem.objects.select_related("order", "product"), pk=item_id
    )

    # Mismo guard que order_item_measurements: sin el, un producto que no usa
    # medidas abria una tabla sin columnas pero con formulario, y al postear el
    # error salia como un "__all__" generico desde OrderItemMeasurement.clean().
    if not item.product.requires_measurements:
        messages.error(request, "Este producto no requiere medidas.")
        if _can_view_item_detail(request, item):
            return redirect("orders:order_item_detail", item_id=item.id)
        # El guardian no puede abrir order_item_detail: mandarlo alli seria un 404.
        return redirect("core:landing")

    if request.method == "POST":
        result = MeasurementGridService.save(item, request.user, request.POST)

        if result.ok:
            for athlete_item in result.changed_athlete_items:
                PiiAuditService.log(
                    request=request,
                    target_user=athlete_item.athlete,
                    access_type="EDIT_MEASUREMENTS",
                    field_accessed="measurements",
                    notes=f"Grid OrderItem pk={item.pk}",
                )
            messages.success(request, "Medidas guardadas correctamente.")
            # Se vuelve al propio grid, no a order_item_detail: esa vista filtra
            # por Order.objects.visible_for_user(), que NO incluye a los
            # guardianes, asi que una tutora guardaba bien y caia en un 404.
            return redirect("orders:item_measurements_grid", item_id=item.id)

        # Un error global (__all__) no tiene celda donde pintarse, asi que se
        # muestra tal cual; si no, el usuario leeria "revisa los campos
        # marcados" sin que ninguno lo este.
        messages.error(
            request,
            result.errors.get("__all__")
            or "Revisa los campos marcados. No se guardó ningún cambio.",
        )
        grid = MeasurementGridService.build(
            item, request.user, values=request.POST, errors=result.errors
        )
        # Un guardado fallido re-renderiza el roster COMPLETO: se ven las
        # medidas igual que en un GET, asi que se audita igual. Sin esto habia
        # un camino para mirar el grid sin dejar rastro.
        _log_grid_view(request, grid, item)
        return render(
            request,
            "orders/items/measurements_grid.html",
            {"grid": grid, "can_view_item_detail": _can_view_item_detail(request, item)},
        )

    grid = MeasurementGridService.build(item, request.user)
    _log_grid_view(request, grid, item)

    return render(
        request,
        "orders/items/measurements_grid.html",
        {"grid": grid, "can_view_item_detail": _can_view_item_detail(request, item)},
    )


@role_required("ADMIN")
@require_POST
def lock_measurements(request, order_id):
    order = get_object_or_404(Order, pk=order_id)

    try:
        MeasurementLifecycleService.lock(order, user=request.user)
        messages.success(request, "Medidas bloqueadas definitivamente")
    except ValidationError as e:
        messages.error(request, e.message if hasattr(e, 'message') else str(e))
    except Exception as e:
        logger.exception("Error inesperado al bloquear medidas order=%s: %s", order_id, e)
        messages.error(request, "Error interno al bloquear medidas. Contacta al soporte.")

    return redirect("orders:admin_order_detail", order_id=order.id)

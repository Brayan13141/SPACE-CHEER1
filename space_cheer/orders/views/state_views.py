from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from orders.models import Order
from orders.services.state import OrderStateService
from django.views.decorators.http import require_POST
from django.core.exceptions import ValidationError, PermissionDenied
from django.contrib.admin.views.decorators import staff_member_required

# ---------------------------------------------------------
# Order State
# ---------------------------------------------------------

# state_views.py


@login_required
@require_POST
def transition_order(request, order_id, to_status):
    """Transición para usuarios normales."""
    _do_transition(request, order_id, to_status)
    return redirect("orders:detail_order", order_id=order_id)


@staff_member_required
@require_POST
def admin_transition_order(request, order_id, to_status):
    """Transición para admin/staff."""
    _do_transition(request, order_id, to_status)
    return redirect("orders:admin_order_detail", order_id=order_id)


def _do_transition(request, order_id, to_status):
    """Lógica común extraída para no duplicar código."""
    VALID_STATUSES = {s for s, _ in Order.STATUS_CHOICES}

    if to_status not in VALID_STATUSES:
        messages.error(request, "Estado inválido.")
        return

    order = get_object_or_404(
        Order.objects.visible_for_user(request.user),
        pk=order_id,
    )

    try:
        OrderStateService.transition(
            order=order,
            to_status=to_status,
            user=request.user,
        )
        messages.success(request, f"Orden actualizada a {to_status}.")

    except ValidationError as e:
        for msg in e.messages:
            messages.error(request, msg)

    except PermissionDenied:
        messages.error(request, "No tienes permisos.")

import logging

from django.contrib.admin.views.decorators import staff_member_required
from django.db import IntegrityError
from django.db.models import Count, Prefetch
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib import messages
from django.views.decorators.http import require_POST
from orders.models import (
    Order,
    OrderItem,
    OrderItemAthlete,
    OrderItemMeasurement,
    OrderLog,
    OrderDesignImage,
)
from orders.services.state import OrderStateService
from orders.forms import OrderDatesForm

logger = logging.getLogger(__name__)


@staff_member_required
def admin_order_list(request):

    status_filter = request.GET.get("status")

    orders = (
        Order.objects.select_related(
            "owner_user",
            "owner_team",
            "created_by",
        )
        .prefetch_related(
            Prefetch(
                "items",
                queryset=OrderItem.objects.select_related("product"),
            )
        )
        .annotate(items_count=Count("items"))
        .order_by("-created_at")
    )

    if status_filter:
        orders = orders.filter(status=status_filter)

    return render(
        request,
        "orders/admin/order_list.html",
        {
            "orders": orders,
            "status_filter": status_filter,
            "status_choices": Order.STATUS_CHOICES,
        },
    )


@staff_member_required
def admin_order_detail(request, order_id):

    order = get_object_or_404(
        Order.objects.select_related(
            "owner_user",
            "owner_team",
            "created_by",
            "contact_info",
            "design_approved_by",
        ).prefetch_related(
            Prefetch(
                "items",
                queryset=OrderItem.objects.select_related(
                    "product",
                    "size_variant",
                ).prefetch_related(
                    Prefetch(
                        "athletes",
                        queryset=OrderItemAthlete.objects.select_related(
                            "athlete"
                        ).prefetch_related(
                            Prefetch(
                                "measurements",
                                queryset=OrderItemMeasurement.objects.select_related(
                                    "field"
                                ),
                            ),
                            "customization",
                        ),
                    )
                ),
            ),
            "design_images",
            Prefetch(
                "orderlog_set",
                queryset=OrderLog.objects.select_related("user"),
            ),
        ),
        pk=order_id,
    )

    dates_form = OrderDatesForm(instance=order)

    available_transitions = OrderStateService.get_available_transitions(
        order,
        request.user,
    )

    return render(
        request,
        "orders/admin/order_detail.html",
        {
            "order": order,
            # ← eliminado "items": order.items.all() — redundante con prefetch
            "dates_form": dates_form,
            "available_transitions": available_transitions,
        },
    )


@staff_member_required
def admin_upload_design(request, order_id):

    order = get_object_or_404(Order, pk=order_id)

    if request.method == "POST":

        image = request.FILES.get("image")
        is_final = request.POST.get("is_final") == "on"

        if not image:
            messages.error(request, "Debes subir una imagen.")
            return redirect("orders:admin_order_detail", order_id=order.id)

        try:
            OrderDesignImage.objects.create(
                order=order,
                image=image,
                uploaded_by=request.user,
                is_final=is_final,
            )
            messages.success(request, "Diseño subido correctamente.")

        except IntegrityError:
            messages.error(
                request,
                "Ya existe un diseño marcado como final. "
                "Desmárcalo antes de subir uno nuevo.",
            )

        return redirect("orders:admin_order_detail", order_id=order.id)

    return render(
        request,
        "orders/admin/upload_design.html",
        {"order": order},
    )


@staff_member_required
@require_POST
def admin_update_order_dates(request, order_id):

    order = get_object_or_404(Order, pk=order_id)

    form = OrderDatesForm(request.POST, instance=order)

    if form.is_valid():
        form.save()
        messages.success(request, "Fechas actualizadas correctamente.")
    else:
        # Extrae todos los errores del form y los muestra
        for field, errors in form.errors.items():
            label = form.fields[field].label if field != "__all__" else "Fechas"
            for error in errors:
                messages.error(request, f"{label}: {error}")

    return redirect("orders:admin_order_detail", order_id=order.id)

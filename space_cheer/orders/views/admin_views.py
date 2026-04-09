import logging
from datetime import datetime
from django.contrib.admin.views.decorators import staff_member_required
from django.db import IntegrityError, transaction
from django.db.models import Count, Prefetch, Q, Sum
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
from django.core.exceptions import ValidationError

from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

logger = logging.getLogger(__name__)


@staff_member_required
def admin_order_list(request):
    status_filter = request.GET.get("status", "")
    type_filter = request.GET.get("type", "")
    search = request.GET.get("q", "").strip()
    date_from = request.GET.get("date_from", "")
    date_to = request.GET.get("date_to", "")
    page_number = request.GET.get("page", 1)
    page_size = request.GET.get("page_size", 15)

    # ─────────────────────────────
    # Query principal
    # ─────────────────────────────
    orders = (
        Order.objects.select_related("owner_user", "owner_team", "created_by")
        .prefetch_related(
            Prefetch("items", queryset=OrderItem.objects.select_related("product"))
        )
        .annotate(
            items_count=Count("items", distinct=True),
            total_amount=Sum("items__subtotal"),
        )
        .order_by("-created_at")
    )

    # ─────────────────────────────
    # Filtros
    # ─────────────────────────────
    if status_filter:
        orders = orders.filter(status=status_filter)

    if type_filter:
        orders = orders.filter(order_type=type_filter)

    if search:
        orders = orders.filter(
            Q(owner_user__first_name__icontains=search)
            | Q(owner_user__last_name__icontains=search)
            | Q(owner_user__email__icontains=search)
            | Q(owner_team__name__icontains=search)
            | Q(created_by__email__icontains=search)
            | Q(id__icontains=search)
        )

    if date_from:
        try:
            orders = orders.filter(
                created_at__date__gte=datetime.strptime(date_from, "%Y-%m-%d").date()
            )
        except ValueError:
            pass

    if date_to:
        try:
            orders = orders.filter(
                created_at__date__lte=datetime.strptime(date_to, "%Y-%m-%d").date()
            )
        except ValueError:
            pass

    # ─────────────────────────────
    # Stats globales (sin filtros)
    # ─────────────────────────────
    all_orders = Order.objects.all()
    stats = {
        "total": all_orders.count(),
        "draft": all_orders.filter(status="DRAFT").count(),
        "pending": all_orders.filter(status="PENDING").count(),
        "design_approved": all_orders.filter(status="DESIGN_APPROVED").count(),
        "in_production": all_orders.filter(status="IN_PRODUCTION").count(),
        "delivered": all_orders.filter(status="DELIVERED").count(),
        "cancelled": all_orders.filter(status="CANCELLED").count(),
    }

    # Cards para template (evita lógica compleja en HTML)
    stats_cards = [
        {"key": "total", "label": "Todas", "color": "primary", "value": stats["total"]},
        {
            "key": "DRAFT",
            "label": "Borrador",
            "color": "secondary",
            "value": stats["draft"],
        },
        {
            "key": "PENDING",
            "label": "Pendiente",
            "color": "warning",
            "value": stats["pending"],
        },
        {
            "key": "IN_PRODUCTION",
            "label": "Producción",
            "color": "primary",
            "value": stats["in_production"],
        },
        {
            "key": "DELIVERED",
            "label": "Entregadas",
            "color": "success",
            "value": stats["delivered"],
        },
        {
            "key": "CANCELLED",
            "label": "Canceladas",
            "color": "danger",
            "value": stats["cancelled"],
        },
    ]

    # ─────────────────────────────
    # Needs attention
    # ─────────────────────────────
    needs_attention = orders.filter(
        Q(status="PENDING", freeze_payment_date__isnull=True)
        | Q(status="PENDING", first_payment_date__isnull=True)
        | Q(status="IN_PRODUCTION", uniform_delivery_date__isnull=True)
    ).values_list("id", flat=True)

    # ─────────────────────────────
    # Paginación
    # ─────────────────────────────
    try:
        page_size = int(page_size)
        if page_size <= 0:
            page_size = 25
    except ValueError:
        page_size = 25

    paginator = Paginator(orders, page_size)

    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    pagination = {
        "total_items": paginator.count,
        "total_pages": paginator.num_pages,
        "current_page": page_obj.number,
        "has_previous": page_obj.has_previous(),
        "has_next": page_obj.has_next(),
        "previous_page": (
            page_obj.previous_page_number() if page_obj.has_previous() else None
        ),
        "next_page": page_obj.next_page_number() if page_obj.has_next() else None,
        "page_range": paginator.get_elided_page_range(
            number=page_obj.number, on_each_side=2, on_ends=1
        ),
        "start_index": page_obj.start_index(),
        "end_index": page_obj.end_index(),
    }

    return render(
        request,
        "orders/admin/order_list.html",
        {
            "page_obj": page_obj,
            "orders": page_obj.object_list,
            "pagination": pagination,
            "status_filter": status_filter,
            "type_filter": type_filter,
            "search": search,
            "date_from": date_from,
            "date_to": date_to,
            "stats": stats,
            "stats_cards": stats_cards,
            "needs_attention": set(needs_attention),
            "request": request,  # 🔥 clave para pagination.html
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
                    ),
                ),
            ),
            "design_images",
            Prefetch("orderlog_set", queryset=OrderLog.objects.select_related("user")),
        ),
        pk=order_id,
    )

    # ── Flags condicionales basados en los productos de la orden ──────────
    items = list(order.items.all())

    order_flags = {
        "requires_design": any(i.product.requires_design for i in items),
        "requires_measurements": any(i.product.requires_measurements for i in items),
        "requires_athletes": any(i.product.requires_athletes for i in items),
        "has_uniforms": any(i.product.product_type == "UNIFORM" for i in items),
        "has_items": bool(items),
    }

    # ── Progreso de medidas ───────────────────────────────────────────────
    measurements_summary = None
    if order_flags["requires_measurements"]:
        total_athletes = 0
        complete_athletes = 0
        for item in items:
            if item.product.requires_measurements:
                for ai in item.athletes.all():
                    total_athletes += 1
                    if ai.has_complete_measurements():
                        complete_athletes += 1
        measurements_summary = {
            "total": total_athletes,
            "complete": complete_athletes,
            "pending": total_athletes - complete_athletes,
            "percent": int(
                (complete_athletes / total_athletes * 100) if total_athletes else 0
            ),
        }

    dates_form = OrderDatesForm(instance=order)
    available_transitions = OrderStateService.get_available_transitions(
        order, request.user
    )
    # ── Measurement actions (UI control) ─────────────────────────────
    measurement_actions = {
        "can_close": (order.measurements_open and not order.measurements_locked),
        "can_reopen": (not order.measurements_locked and order.can_edit_general()),
        "can_lock": (
            not order.measurements_locked and order_flags["requires_measurements"]
        ),
    }

    return render(
        request,
        "orders/admin/order_detail.html",
        {
            "order": order,
            "dates_form": dates_form,
            "available_transitions": available_transitions,
            "order_flags": order_flags,
            "measurements_summary": measurements_summary,
            "measurement_actions": measurement_actions,  # 👈 AÑADE ESTO
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

        ALLOWED_TYPES = ["image/jpeg", "image/png", "image/webp"]
        MAX_SIZE_MB = 10

        if image.content_type not in ALLOWED_TYPES:
            messages.error(request, "Solo se permiten imágenes JPG, PNG o WEBP.")
            return redirect("orders:admin_order_detail", order_id=order.id)

        if image.size > MAX_SIZE_MB * 1024 * 1024:
            messages.error(request, f"El tamaño máximo permitido es {MAX_SIZE_MB} MB.")
            return redirect("orders:admin_order_detail", order_id=order.id)

        try:
            with transaction.atomic():
                #  Validación previa (mejor UX que depender del DB error)
                if is_final and order.design_images.filter(is_final=True).exists():
                    raise ValidationError(
                        "Ya existe un diseño marcado como final. "
                        "Desmárcalo antes de subir uno nuevo."
                    )

                OrderDesignImage.objects.create(
                    order=order,
                    image=image,
                    uploaded_by=request.user,
                    is_final=is_final,
                )

            messages.success(request, "Diseño subido correctamente.")

        except ValidationError as e:
            messages.error(request, str(e))

        except IntegrityError:
            # fallback por si hay constraint en DB
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

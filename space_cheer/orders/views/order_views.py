from accounts.decorators import role_required
from django.shortcuts import render, get_object_or_404, redirect
from django.core.exceptions import PermissionDenied, ValidationError
from django.contrib import messages
from orders.models import Order, OrderItem
from orders.services.sizes.SizeSummaryService import SizeSummaryService
from orders.services.state import OrderCreationService, OrderStateService
from orders.services.factories import OrderContactInfoFactory
from orders.services.preconditions import can_submit_order
from teams.models import Team
from django.db import transaction
from django.db.models import Exists, OuterRef
from orders.services.preconditions import OrderBlockingIssue
from orders.pagination import OrderPaginator

# from orders.services.logging_service import OrderLogger
# import logging

# logger = logging.getLogger(__name__)


@role_required("ATHLETE", "HEADCOACH", "COACH","GUARDIAN","ADMIN")
def order_list(request):
    """
    Lista de órdenes visibles para el usuario.
    Permite filtrar activas vs finalizadas.

    **CON PAGINACIÓN**
    """
    filter_status = request.GET.get("filter", "active")
    page_number = request.GET.get("page", 1)

    orders = (
        Order.objects.visible_for_user(request.user)
        .select_related(
            "owner_user",
            "owner_team",
            "created_by",
        )
        .annotate(
            has_design_items=Exists(
                OrderItem.objects.filter(
                    order=OuterRef("pk"),
                    product__usage_type__in=["TEAM_CUSTOM", "ATHLETE_CUSTOM"],
                )
            )
        )
    )

    if filter_status == "finalized":
        orders = orders.filter(status__in=["DELIVERED", "CANCELLED"])
    else:
        orders = orders.exclude(status__in=["DELIVERED", "CANCELLED"])

    #  PAGINACIÓN
    page_obj, pagination_info = OrderPaginator.paginate(
        queryset=orders.order_by("-created_at").distinct(),
        page_number=page_number,
    )

    return render(
        request,
        "orders/users/order_list.html",
        {
            "page_obj": page_obj,  # ← Cambio de "orders" a "page_obj"
            "orders": page_obj.object_list,
            "pagination": pagination_info,  # ← Metadata
            "filter_status": filter_status,
        },
    )


@role_required("ATHLETE", "HEADCOACH", "COACH", "ADMIN", "GUARDIAN")
def create_order(request):
    """
    Crear una orden TEAM o PERSONAL.
    """

    if request.user.is_minor:
        messages.error(request, "Los atletas menores no pueden crear pedidos. Tu tutor debe hacerlo.")
        return redirect("guardian:minor_blocked")

    teams = Team.objects.filter(coach=request.user)

    if request.method == "POST":

        order_type = request.POST.get("order_type")
        order_team_id = request.POST.get("team_id") or ""

        if order_type not in ["PERSONAL", "TEAM"]:
            return render(
                request,
                "orders/users/order_create.html",
                {"teams": teams, "error": "Tipo de orden inválido."},
            )

        team = None

        if order_type == "TEAM":

            if not teams.exists():
                return render(
                    request,
                    "orders/users/order_create.html",
                    {"teams": teams, "error": "No puedes crear órdenes de equipo."},
                )

            if not order_team_id:
                return render(
                    request,
                    "orders/users/order_create.html",
                    {"teams": teams, "error": "Debes seleccionar un equipo."},
                )

            try:
                team = teams.get(id=order_team_id)
            except Team.DoesNotExist:
                return render(
                    request,
                    "orders/users/order_create.html",
                    {"teams": teams, "error": "Equipo inválido."},
                )

        try:
            with transaction.atomic():
                order = OrderCreationService.create_order(
                    order_type=order_type,
                    created_by=request.user,
                    owner_user=request.user if order_type == "PERSONAL" else None,
                    owner_team=team,
                )
                contact_info = OrderContactInfoFactory.from_user(
                    order=order, user=request.user
                )
                contact_info.full_clean()
                contact_info.save()

                # LOGGING
                # OrderLogger.log_order_created(order, request.user)

        except ValidationError as e:
            # logger.error(f"Order creation failed: {e}", extra={"user": request.user.id})

            return render(
                request,
                "orders/users/order_create.html",
                {"teams": teams, "error": e.messages[0]},
            )

        return redirect("orders:contact_info_order", order_id=order.id)

    return render(
        request,
        "orders/users/order_create.html",
        {"teams": teams},
    )


@role_required("ATHLETE", "HEADCOACH", "COACH", "ADMIN", "GUARDIAN")
def order_edit(request, order_id):
    """
    Editar notas de diseño de la orden.
    """

    order = get_object_or_404(
        Order.objects.visible_for_user(request.user),
        pk=order_id,
    )

    if not order.can_edit_general():
        messages.error(request, "La orden ya está cerrada o en producción y no se pueden hacer cambios.")
        return redirect("orders:detail_order", order_id=order.id)

    if request.method == "POST":
        order.design_notes = request.POST.get("design_notes", "").strip()[:5000]
        order.save(update_fields=["design_notes", "updated_at"])

        return redirect("orders:detail_order", order_id=order.id)

    return render(
        request,
        "orders/users/order_edit.html",
        {"order": order},
    )


@role_required("ATHLETE", "HEADCOACH", "COACH", "ADMIN", "GUARDIAN")
def order_contact_info(request, order_id):

    order = get_object_or_404(
        Order,
        id=order_id,
        created_by=request.user,
    )

    if not order.can_edit_general():
        messages.error(request, "La orden ya está cerrada o en producción y no se puede editar el contacto.")
        return redirect("orders:detail_order", order_id=order.id)

    # Obtener o crear contact_info
    if not order.has_contact_info():
        contact_info = OrderContactInfoFactory.from_user(order=order, user=request.user)
        contact_info.save()
    else:
        contact_info = order.contact_info
        if contact_info.closed:
            messages.error(request, "La información de envío está cerrada y no puede ser modificada.")
            return redirect("orders:detail_order", order_id=order.id)

    if request.method == "POST":
        contact_info.contact_name = request.POST.get("contact_name", "")
        contact_info.contact_phone = request.POST.get("contact_phone", "")
        contact_info.contact_email = request.POST.get("contact_email", "")
        contact_info.shipping_address_line = request.POST.get(
            "shipping_address_line", ""
        )
        contact_info.shipping_city = request.POST.get("shipping_city", "")
        contact_info.shipping_postal_code = request.POST.get("shipping_postal_code", "")

        try:
            contact_info.full_clean()
            contact_info.save()
            return redirect("orders:detail_order", order_id=order.id)

        except ValidationError as e:
            return render(
                request,
                "orders/users/order_contact_info.html",
                {"order": order, "contact_info": contact_info, "errors": e.messages},
            )

    return render(
        request,
        "orders/users/order_contact_info.html",
        {"order": order, "contact_info": contact_info},
    )


@role_required("ATHLETE", "HEADCOACH", "COACH", "ADMIN", "GUARDIAN")
def order_detail(request, order_id):

    order = get_object_or_404(
        Order.objects.visible_for_user(request.user)
        .select_related("owner_user", "owner_team", "created_by", "contact_info")
        .prefetch_related(
            "items__product",
            "items__size_variant",
            "items__athletes__athlete",
            "items__athletes__measurements",
            "items__athletes__customization",
            "design_images",
            "orderlog_set",
        ),
        pk=order_id,
    )

    items = list(order.items.all())
    order_flags = {
        "requires_design": any(i.product.requires_design for i in items),
        "requires_measurements": any(i.product.requires_measurements for i in items),
        "requires_athletes": any(i.product.requires_athletes for i in items),
        "has_uniforms": any(i.product.product_type == "UNIFORM" for i in items),
        "has_items": bool(items),
        "is_simple": bool(items) and all(i.product.is_simple for i in items),
    }

    # Blocking issues solo aplican cuando la orden está en DRAFT (el usuario va a enviarla)
    blocking_issues = []
    if order.status == "DRAFT":
        try:
            Order.validate_order_ready(order)
        except ValidationError as e:
            for msg in e.messages:
                blocking_issues.append(
                    OrderBlockingIssue(code="ORDER_NOT_READY", message=msg)
                )
        blocking_issues += can_submit_order(order)

    available_transitions = OrderStateService.get_available_transitions(
        order, request.user
    )

    transition_labels = {
        "PENDING": "Enviar pedido",
        "CANCELLED": "Cancelar pedido",
        "DESIGN_APPROVED": "Aprobar diseño",
        "IN_PRODUCTION": "Iniciar producción",
        "DELIVERED": "Marcar como entregada",
    }

    # Los items por talla se agrupan por producto: son N filas del MISMO
    # producto y un solo roster, asi que una sola tarjeta y un solo boton.
    size_groups = SizeSummaryService.for_order(order)

    return render(
        request,
        "orders/users/order_detail.html",
        {
            "order": order,
            "order_flags": order_flags,
            "blocking_issues": blocking_issues,
            "size_groups": size_groups,
            # La tarjeta del grupo ya muestra cada talla con su cantidad y su
            # precio, asi que el bucle de productos salta esos items; si no,
            # cada talla vuelve a salir como tarjeta suelta debajo.
            "size_group_item_ids": {
                item_id for grupo in size_groups for item_id in grupo.item_ids
            },
            "available_transitions": available_transitions,
            "transition_labels": transition_labels,
        },
    )

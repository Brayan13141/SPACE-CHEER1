"""Vistas admin de pedidos personales (offline)."""
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.decorators import role_required
from orders.models import Customer, Order, OrderItem
from orders.services.offline import OfflineOrderService
from production.models import ProductionTemplate
from products.models import Product


@role_required("ADMIN")
def offline_order_create(request):
    if request.method == "POST":
        try:
            order = _create_from_post(request)
        except (ValidationError, ValueError, InvalidOperation, KeyError) as exc:
            messages.error(request, f"No se pudo crear el pedido: {exc}")
            return redirect("orders:offline_order_create")
        messages.success(request, f"Pedido offline #{order.pk} creado.")
        return redirect("orders:admin_order_detail", order.pk)

    context = {
        "customers": Customer.objects.all(),
        "internal_products": Product.objects.filter(scope="INTERNAL", is_active=True),
        "templates": ProductionTemplate.objects.all(),
    }
    return render(request, "orders/admin/offline_create.html", context)


def _create_from_post(request):
    post = request.POST
    customer_id = None
    customer_data = None
    if post.get("customer_mode") == "existing":
        customer_id = int(post["customer_id"])
    else:
        customer_data = {
            "name": post.get("customer_name", "").strip(),
            "phone": post.get("customer_phone", "").strip(),
            "email": post.get("customer_email", "").strip(),
            "notes": post.get("customer_notes", "").strip(),
        }
        if post.get("customer_user_id"):
            customer_data["user_id"] = int(post["customer_user_id"])

    items = []
    total_rows = int(post.get("items-TOTAL", 0))
    for i in range(total_rows):
        prefix = f"items-{i}-"
        if not any(k.startswith(prefix) for k in post):
            continue
        item = {
            "quantity": int(post.get(f"{prefix}quantity", 1)),
            "talla": post.get(f"{prefix}talla", "").strip(),
            "notas": post.get(f"{prefix}notas", "").strip(),
        }
        if post.get(f"{prefix}product_id"):
            item["product_id"] = int(post[f"{prefix}product_id"])
        elif post.get(f"{prefix}new_product_name"):
            item["new_product"] = {
                "name": post[f"{prefix}new_product_name"].strip(),
                "base_price": post.get(f"{prefix}new_product_price", "0"),
                "description": post.get(f"{prefix}new_product_description", ""),
            }
            if post.get(f"{prefix}new_product_template"):
                item["new_product"]["template_id"] = int(post[f"{prefix}new_product_template"])
        else:
            continue
        items.append(item)

    initial_payment = None
    if post.get("initial_payment_amount"):
        initial_payment = {
            "amount": Decimal(post["initial_payment_amount"]),
            "method": post.get("initial_payment_method", "CASH"),
            "notes": post.get("initial_payment_notes", ""),
        }

    return OfflineOrderService.create(
        admin_user=request.user,
        customer_id=customer_id,
        customer_data=customer_data,
        items=items,
        agreed_price=Decimal(post["agreed_price"]),
        delivery_date=post.get("delivery_date") or None,
        notes=post.get("notes", ""),
        initial_payment=initial_payment,
    )


@role_required("ADMIN")
def customer_list(request):
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        if not name:
            messages.error(request, "El nombre es obligatorio.")
        else:
            Customer.objects.create(
                name=name,
                phone=request.POST.get("phone", "").strip(),
                email=request.POST.get("email", "").strip(),
                notes=request.POST.get("notes", "").strip(),
                created_by=request.user,
            )
            messages.success(request, f"Cliente «{name}» creado.")
        return redirect("orders:customer_list")

    q = request.GET.get("q", "").strip()
    customers = Customer.objects.all()
    if q:
        customers = customers.filter(Q(name__icontains=q) | Q(phone__icontains=q))
    return render(request, "orders/admin/customers.html", {"customers": customers, "q": q})


@role_required("ADMIN")
@require_POST
def register_payment(request, order_id):
    order = get_object_or_404(Order, pk=order_id, order_type="OFFLINE")
    try:
        OfflineOrderService.add_payment(
            order=order, admin_user=request.user,
            amount=Decimal(request.POST["amount"]),
            method=request.POST.get("method", "CASH"),
            notes=request.POST.get("notes", ""),
        )
        messages.success(request, "Abono registrado.")
    except (ValidationError, InvalidOperation, KeyError) as exc:
        messages.error(request, f"No se pudo registrar el abono: {exc}")
    return redirect("orders:admin_order_detail", order.pk)


@role_required("ADMIN")
@require_POST
def offline_item_measurements(request, item_id):
    item = get_object_or_404(
        OrderItem.objects.select_related("order"),
        pk=item_id, order__order_type="OFFLINE",
    )
    if not item.order.can_edit_general():
        messages.error(request, "La orden ya no es editable.")
        return redirect("orders:admin_order_detail", item.order_id)

    medidas = {}
    for field in item.product.measurement_fields.select_related("field").all():
        slug = field.field.slug
        value = request.POST.get(f"medida-{slug}", "").strip()
        if value:
            medidas[slug] = value
    OfflineOrderService.save_item_measurements(
        item=item,
        talla=request.POST.get("talla", "").strip(),
        notas=request.POST.get("notas", "").strip(),
        medidas=medidas,
    )
    messages.success(request, "Medidas actualizadas.")
    return redirect("orders:admin_order_detail", item.order_id)

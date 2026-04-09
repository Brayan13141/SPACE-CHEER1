from django.shortcuts import render, redirect, get_object_or_404
from django.core.exceptions import ValidationError, PermissionDenied
from django.db.models import Prefetch
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from orders.models import Order
from orders.services.product_filter_service import ProductFilterService
from orders.services.servicesItems.order_item_service import OrderItemService
from products.models import Product, ProductSizeVariant, Season

# ---------------------------------------------------------
# Products
# ---------------------------------------------------------


@login_required
def order_add_product(request, order_id):
    """
    Agregar productos a una orden.
    """

    order = get_object_or_404(
        Order.objects.visible_for_user(request.user),
        pk=order_id,
    )

    if not order.can_edit_general():
        messages.error(request, "La orden no se puede modificar.")
        return redirect("orders:detail_order", order_id=order.id)

    products_qs = (
        ProductFilterService.filter_for_order(
            order=order,
            filters=request.GET,
        )
        .filter(is_configured=True)
        .select_related(
            "season",
            "owner_team",
        )
        .prefetch_related(
            Prefetch(
                "size_variants", queryset=ProductSizeVariant.objects.order_by("size")
            ),
            "measurement_fields__field",
        )
    )

    if request.method == "POST":

        product_id = request.POST.get("product_id")

        try:
            quantity = int(request.POST.get("quantity", 1))
            quantity = max(1, min(quantity, 500))
        except (TypeError, ValueError):
            messages.error(request, "Cantidad inválida.")
            return redirect("orders:add_item_product_order", order_id=order.id)

        product = get_object_or_404(products_qs, pk=product_id)
        size_variant_id = request.POST.get("size_variant")
        size_variant = None

        if size_variant_id:
            size_variant = get_object_or_404(
                ProductSizeVariant, pk=size_variant_id, product=product
            )

        try:

            item = OrderItemService.add_product(
                order=order,
                product=product,
                quantity=quantity,
                size_variant=size_variant,
            )

            messages.success(request, "Producto agregado correctamente.")

            # Si requiere configuración posterior
            if product.usage_type in ["TEAM_CUSTOM", "ATHLETE_CUSTOM"]:
                return redirect(
                    "orders:order_item_detail",
                    item_id=item.id,
                )

            return redirect("orders:detail_order", order_id=order.id)

        except ValidationError as e:
            if hasattr(e, "message_dict"):
                for field, errors in e.message_dict.items():
                    for msg in errors:
                        messages.error(request, msg)
            else:
                for msg in e.messages:
                    messages.error(request, msg)

            return redirect("orders:detail_order", order_id=order.id)

    seasons = Season.objects.filter(is_active=True)

    return render(
        request,
        "orders/products/add_product.html",
        {
            "order": order,
            "products": products_qs,
            "seasons": seasons,
            "product_type_choices": Product.PRODUCT_TYPE_CHOICES,
            "usage_type_choices": Product.USAGE_TYPE_CHOICES,
        },
    )

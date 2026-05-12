from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from orders.models import Order
from orders.services.cart import CartService
from teams.models import Team


@login_required
@require_POST
def cart_add(request, product_pk):
    from orders.services.cart import CartService
    from products.models import Product

    if request.user.is_minor:
        messages.error(request, "Los atletas menores no pueden crear pedidos. Tu tutor debe hacerlo.")
        return redirect("guardian:minor_blocked")

    catalog_qs = CartService.get_catalog_queryset(request.user)
    product = get_object_or_404(catalog_qs, pk=product_pk)

    needs_team = (
        product.scope == 'TEAM_ONLY'
        or product.usage_type in ['TEAM_CUSTOM', 'ATHLETE_CUSTOM']
    )

    if not needs_team:
        try:
            order = CartService.get_or_create_draft(user=request.user, order_type='PERSONAL')
        except Exception as e:
            messages.error(request, f"No se pudo crear el pedido: {e}")
            return redirect('products:catalog')
        return redirect('orders:add_item_product_order', order_id=order.pk)

    # Producto que requiere equipo
    if product.scope == 'TEAM_ONLY':
        # Equipo ya determinado por el producto
        team = product.owner_team
        if team.coach != request.user:
            messages.error(request, "No tienes acceso a este producto.")
            return redirect('products:catalog')
        try:
            order = CartService.get_or_create_draft(user=request.user, order_type='TEAM', team=team)
        except Exception as e:
            messages.error(request, f"No se pudo crear el pedido: {e}")
            return redirect('products:catalog')
        return redirect('orders:add_item_product_order', order_id=order.pk)

    # TEAM_CUSTOM / ATHLETE_CUSTOM con scope=CATALOG — necesita seleccionar equipo
    team_id = request.POST.get('team_id')
    if not team_id:
        return redirect('orders:cart_team_select', product_pk=product.pk)

    team = get_object_or_404(Team, pk=team_id, coach=request.user)
    try:
        order = CartService.get_or_create_draft(user=request.user, order_type='TEAM', team=team)
    except Exception as e:
        messages.error(request, f"No se pudo crear el pedido: {e}")
        return redirect('products:catalog')
    return redirect('orders:add_item_product_order', order_id=order.pk)


@login_required
def cart_team_select(request, product_pk):
    from orders.services.cart import CartService

    catalog_qs = CartService.get_catalog_queryset(request.user)
    product = get_object_or_404(catalog_qs, pk=product_pk)

    teams = Team.objects.filter(coach=request.user)
    if not teams.exists():
        messages.error(request, "No tienes equipos para crear un pedido de equipo.")
        return redirect('products:catalog')

    return render(request, 'orders/cart/cart_team_select.html', {
        'product': product,
        'teams': teams,
    })


@login_required
def cart_view(request):
    draft_orders = (
        Order.objects.visible_for_user(request.user)
        .filter(status='DRAFT')
        .select_related('owner_team', 'owner_user')
        .prefetch_related('items__product')
        .order_by('-created_at')
    )
    return render(request, 'orders/cart/cart.html', {
        'draft_orders': draft_orders,
    })

from orders.models import Order, OrderItem


def cart_context(request):
    if not request.user.is_authenticated:
        return {'cart_count': 0}
    draft_orders = Order.objects.visible_for_user(request.user).filter(status='DRAFT')
    cart_count = OrderItem.objects.filter(order__in=draft_orders).count()
    return {'cart_count': cart_count}

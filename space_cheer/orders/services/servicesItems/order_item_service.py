from django.core.exceptions import ValidationError
from django.db import transaction
from orders.models import OrderItem
from orders.services.servicesItems.product_selector import (
    available_products_for_order,
)


class OrderItemService:
    @staticmethod
    @transaction.atomic
    def add_product(order, product, quantity=1, size_variant=None):

        if not order.can_edit_general():
            raise ValidationError("La orden no es editable")

        if quantity < 1:
            raise ValidationError("La cantidad debe ser mayor a cero")

        if not available_products_for_order(order).filter(pk=product.pk).exists():
            raise ValidationError("Este producto no está permitido para esta orden")

        # Validar talla si es necesaria
        if product.size_strategy == "STANDARD" and not size_variant:
            raise ValidationError("Debe seleccionar una talla")

        if product.size_strategy != "STANDARD":
            size_variant = None

        # evitar duplicado con misma talla
        existing_item = order.items.filter(
            product=product, size_variant=size_variant
        ).first()

        # CORRECCIÓN
        if existing_item:
            if product.usage_type == "ATHLETE_CUSTOM":
                raise ValidationError(
                    "Para productos personalizados por atleta, agrega atletas individualmente "
                    "en lugar de incrementar cantidad directamente."
                )
            existing_item.quantity += quantity
            existing_item.save()
            order.invalidate_cache()
            return existing_item

        result = OrderItem.objects.create(
            order=order,
            product=product,
            quantity=quantity,
            size_variant=size_variant,
        )
        order.invalidate_cache()
        return result

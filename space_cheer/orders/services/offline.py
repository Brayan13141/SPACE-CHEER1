"""
Servicio de pedidos personales (offline): captura por admin de encargos
hechos en persona/WhatsApp, con productos INTERNAL y control de pagos.
"""
import logging
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

logger = logging.getLogger(__name__)


class OfflineOrderService:

    @classmethod
    @transaction.atomic
    def create(cls, *, admin_user, customer_id=None, customer_data=None,
               items, agreed_price, delivery_date=None, notes="",
               initial_payment=None):
        from orders.models import Customer, Order, OrderItem
        from orders.services.state import OrderStateService

        if not items:
            raise ValidationError("El pedido debe tener al menos un producto")

        customer = cls._resolve_customer(admin_user, customer_id, customer_data)

        order = Order(
            order_type="OFFLINE",
            customer=customer,
            created_by=admin_user,
            agreed_price=agreed_price,
            design_notes=notes,
            uniform_delivery_date=delivery_date,
            measurements_open=False,
        )
        order._allow_status_change = False
        order.save()

        for item_data in items:
            product = cls._resolve_product(admin_user, item_data)
            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=int(item_data.get("quantity", 1)),
                custom_measurements={
                    "talla": item_data.get("talla", ""),
                    "notas": item_data.get("notas", ""),
                    "medidas": {},
                },
            )

        order = OrderStateService.transition(order, "PENDING", admin_user)

        if initial_payment and initial_payment.get("amount"):
            cls.add_payment(
                order=order, admin_user=admin_user,
                amount=initial_payment["amount"],
                method=initial_payment.get("method", "CASH"),
                notes=initial_payment.get("notes", ""),
            )

        logger.info(
            "Pedido offline #%s creado por %s (cliente=%s, total=$%s)",
            order.pk, admin_user, customer, agreed_price,
        )
        return order

    @staticmethod
    @transaction.atomic
    def add_payment(*, order, admin_user, amount, method="CASH", notes=""):
        from orders.models import Order, OrderPayment

        # Bloquea la fila de la orden para serializar abonos concurrentes:
        # la segunda llamada espera a que la primera confirme antes de leer
        # total_paid, así su validación de sobrepago ve el pago ya aplicado.
        order = Order.objects.select_for_update().get(pk=order.pk)

        return OrderPayment.objects.create(
            order=order, amount=Decimal(amount), method=method,
            notes=notes, registered_by=admin_user,
        )

    @staticmethod
    def save_item_measurements(*, item, talla=None, notas=None, medidas=None):
        """Actualiza el JSON de medidas de un item offline (mientras sea editable)."""
        data = item.custom_measurements or {"talla": "", "notas": "", "medidas": {}}
        if talla is not None:
            data["talla"] = talla
        if notas is not None:
            data["notas"] = notas
        if medidas is not None:
            data["medidas"] = medidas
        item.custom_measurements = data
        item.save(update_fields=["custom_measurements"])
        return item

    # -------------------------------------------------------------
    @staticmethod
    def _resolve_customer(admin_user, customer_id, customer_data):
        from accounts.models import User
        from orders.models import Customer

        if customer_id:
            return Customer.objects.get(pk=customer_id)
        if not customer_data or not customer_data.get("name"):
            raise ValidationError("Falta el cliente del pedido")
        user = None
        if customer_data.get("user_id"):
            user = User.objects.get(pk=customer_data["user_id"])
        return Customer.objects.create(
            name=customer_data["name"],
            phone=customer_data.get("phone", ""),
            email=customer_data.get("email", ""),
            notes=customer_data.get("notes", ""),
            user=user,
            created_by=admin_user,
        )

    @staticmethod
    def _resolve_product(admin_user, item_data):
        from products.models import Product, Season

        if item_data.get("product_id"):
            product = Product.objects.get(pk=item_data["product_id"])
            if product.scope != "INTERNAL":
                raise ValidationError(
                    f"El producto '{product.name}' no es interno de taller"
                )
            return product

        new_data = item_data.get("new_product")
        if not new_data or not new_data.get("name"):
            raise ValidationError("Cada item requiere un producto existente o uno nuevo")

        season = Season.objects.filter(is_active=True).first()
        if season is None:
            raise ValidationError("No hay temporada activa para crear el producto")

        product = Product(
            name=new_data["name"],
            description=new_data.get("description", ""),
            product_type=new_data.get("product_type", "OTHER"),
            usage_type="GLOBAL",
            scope="INTERNAL",
            size_strategy="NONE",
            base_price=Decimal(new_data["base_price"]),
            season=season,
            is_active=True,
        )
        product.save()

        template_id = new_data.get("template_id")
        if template_id:
            from production.models import ProductionTemplate, ProductStageConfig

            template = ProductionTemplate.objects.get(pk=template_id)
            for ts in template.template_stages.select_related("stage").all():
                ProductStageConfig.objects.create(
                    product=product, stage=ts.stage,
                    display_order=ts.display_order,
                )
        return product

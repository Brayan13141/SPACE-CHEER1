from django.core.exceptions import ValidationError
from django.db import transaction
from orders.models import OrderItemAthlete
from orders.services.validators import OrderAthleteValidator


class OrderItemAthleteService:
    @staticmethod
    @transaction.atomic
    def add_athlete(order_item, athlete):
        product = order_item.product
        order = order_item.order

        #  Validaciones de dominio existentes
        OrderAthleteValidator.validate_athlete_for_order(order, athlete)
        OrderAthleteValidator.validate_not_duplicated(order_item, athlete)

        athlete_item = OrderItemAthlete.objects.create(
            order_item=order_item,
            athlete=athlete,
        )

        #  Snapshot automático de medidas base
        OrderItemAthleteService._create_measurement_snapshot(athlete_item)

        return athlete_item

    @staticmethod
    def _create_measurement_snapshot(athlete_item):
        """
        Crea snapshot de los campos de medida requeridos por el producto.
        """
        product = athlete_item.order_item.product

        for pmf in product.measurement_fields.all():
            athlete_item.measurements.create(
                field=pmf.field,
                field_name=pmf.field.name,
                field_unit=pmf.field.unit,
                value="",  # vacío hasta que usuario lo complete
            )

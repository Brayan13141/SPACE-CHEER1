# orders/services/measurements.py
from django.core.exceptions import ValidationError
from django.db import transaction
from measures.models import MeasurementField, MeasurementValue
from orders.models import OrderItemMeasurement


class OrderMeasurementService:
    """
    Maneja la copia y validación de medidas desde el perfil del atleta
    hacia un item del pedido (snapshot).
    """

    @staticmethod
    def populate_from_profile(order_item, athlete):
        """
        Copia las medidas del atleta hacia el OrderItemAthlete correspondiente
        """

        order = order_item.order
        if order.measurements_locked:
            raise ValidationError("Las medidas están bloqueadas")

        # 1. Validar estado de la orden
        if not order.can_edit_general():
            raise ValidationError(
                "La orden no permite modificar medidas en este estado"
            )
        if not order.can_edit_measurements():
            raise ValidationError("La orden no permite modificar medidas ahora")
        # 2. Buscar el OrderItemAthlete
        try:
            athlete_item = order_item.athletes.get(athlete=athlete)
        except order_item.athletes.model.DoesNotExist:
            raise ValidationError(
                "El atleta no está asignado a este producto del pedido"
            )

        # 3. Obtener campos de medida activos
        product = order_item.product
        # Obtener SOLO los campos del producto
        product_measurement_fields = product.measurement_fields.select_related(
            "field"
        ).all()
        fields_ids = [pmf.field_id for pmf in product_measurement_fields]
        fields = MeasurementField.objects.filter(id__in=fields_ids, is_active=True)

        if not fields.exists():
            return  # no hay medidas configuradas

        # 4. Obtener medidas base del atleta
        base_measurements = {
            mv.field_id: mv
            for mv in MeasurementValue.objects.filter(user=athlete, field__in=fields)
        }

        errors = []
        for field in fields:
            base_value = base_measurements.get(field.id)
            if field.required and not base_value:
                errors.append(
                    f"El atleta {athlete} no tiene la medida requerida: {field.name}"
                )

        if errors:
            raise ValidationError(errors)  # falla antes de tocar la DB

        with transaction.atomic():
            for field in fields:
                base_value = base_measurements.get(field.id)
                if not base_value:
                    continue
                OrderItemMeasurement.objects.update_or_create(
                    athlete_item=athlete_item,
                    field=field,
                    defaults={
                        "value": base_value.value,
                        "field_name": field.name,
                        "field_unit": field.unit,
                    },
                )

    @staticmethod
    def save_measurement(athlete_item, field, value):
        order = athlete_item.order_item.order
        product = athlete_item.order_item.product

        if not order.can_edit_general():
            raise ValidationError("La orden no permite modificar medidas en esta etapa")

        # Solo ATHLETE_CUSTOM permite medidas
        if not product.requires_measurements:
            raise ValidationError("Este producto no requiere medidas personalizadas")

        measurement, _ = OrderItemMeasurement.objects.update_or_create(
            athlete_item=athlete_item,
            field=field,
            defaults={"value": value},
        )

        return measurement

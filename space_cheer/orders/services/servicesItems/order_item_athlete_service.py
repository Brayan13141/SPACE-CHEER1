from decimal import Decimal, InvalidOperation
from django.core.exceptions import ValidationError
from django.db import transaction
from orders.models import OrderItemAthlete, OrderItemMeasurement
from orders.services.validators import OrderAthleteValidator


class OrderItemAthleteService:

    @staticmethod
    @transaction.atomic
    def add_athlete(order_item, athlete):
        order = order_item.order

        OrderAthleteValidator.validate_athlete_for_order(order, athlete)
        OrderAthleteValidator.validate_not_duplicated(order_item, athlete)

        athlete_item = OrderItemAthlete.objects.create(
            order_item=order_item,
            athlete=athlete,
        )

        OrderItemAthleteService._create_measurement_snapshot(athlete_item)
        return athlete_item

    @staticmethod
    def _create_measurement_snapshot(athlete_item):
        """
        Crea snapshot fiel de las medidas del atleta.
        - Si tiene valor: lo copia tal cual (string)
        - Si no tiene valor: guarda "" (vacío, no None)
        - NO hace juicios sobre si el valor es válido o no
        """
        product = athlete_item.order_item.product
        athlete = athlete_item.athlete

        # Dict: field_id → valor string (o None si no existe)
        athlete_measurements = {
            m.field_id: m.value
            for m in athlete.measurements.all()
            # m.value es CharField, puede ser "" pero no None
        }

        snapshots = []

        for pmf in product.measurement_fields.select_related("field").all():
            field = pmf.field

            # Lo que tiene el atleta (string) o None si no tiene el campo
            raw_value = athlete_measurements.get(pmf.field_id)

            # Normalización: None → "" para consistencia
            # El valor "" significa "no tiene esta medida aún"
            snapshot_value = raw_value if raw_value is not None else ""

            snapshots.append(
                OrderItemMeasurement(
                    athlete_item=athlete_item,
                    field=field,
                    field_name=field.name,
                    field_unit=field.unit,
                    value_original=snapshot_value,
                    value=snapshot_value,
                    is_modified=False,
                )
            )

        if snapshots:
            OrderItemMeasurement.objects.bulk_create(
                snapshots,
                update_conflicts=True,
                unique_fields=["athlete_item", "field"],
                # NO actualizar is_modified — respetar ediciones previas
                update_fields=["value_original", "value"],
            )

    @staticmethod
    @transaction.atomic
    def sync_measurements_from_athlete(athlete_item):
        """
        Sincroniza medidas del perfil del atleta al snapshot de la orden.

        Reglas:
        - Si el row tiene is_modified=True: NO tocar (el coach editó manualmente)
        - Si el valor cambió en el perfil: actualizar value y value_original
        - Si existe un campo nuevo en el producto que no tiene row: crearlo
        - Si el atleta no tiene la medida: dejar "" (no None)
        """
        athlete = athlete_item.athlete
        product = athlete_item.order_item.product

        # Medidas actuales del perfil del atleta
        # key: field_id, value: string tal cual (CharField)
        athlete_measurements = {m.field_id: m.value for m in athlete.measurements.all()}

        # Rows existentes en la orden para este atleta+item
        existing_measurements = {m.field_id: m for m in athlete_item.measurements.all()}

        # Campos configurados en el producto (fuente de verdad del schema)
        product_fields = list(product.measurement_fields.select_related("field").all())

        updates = []
        new_snapshots = []

        for pmf in product_fields:
            field_id = pmf.field_id
            field = pmf.field

            # Valor del perfil del atleta ("" si no tiene esa medida)
            profile_value = athlete_measurements.get(field_id, "")

            if field_id in existing_measurements:
                # ── Row ya existe ──────────────────────────────────────
                measurement = existing_measurements[field_id]

                # Respetar edición manual del coach
                if measurement.is_modified:
                    continue

                # Solo actualizar si realmente cambió
                if measurement.value != profile_value:
                    measurement.value = profile_value
                    measurement.value_original = profile_value
                    updates.append(measurement)

            else:
                # ── Row no existe (campo nuevo en el producto) ─────────
                new_snapshots.append(
                    OrderItemMeasurement(
                        athlete_item=athlete_item,
                        field=field,
                        field_name=field.name,
                        field_unit=field.unit,
                        value_original=profile_value,
                        value=profile_value,
                        is_modified=False,
                    )
                )

        if updates:
            OrderItemMeasurement.objects.bulk_update(
                updates,
                ["value", "value_original"],
            )

        if new_snapshots:
            OrderItemMeasurement.objects.bulk_create(
                new_snapshots,
                update_conflicts=True,
                unique_fields=["athlete_item", "field"],
                update_fields=["value_original", "value"],
            )

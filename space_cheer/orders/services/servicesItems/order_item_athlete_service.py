from decimal import Decimal, InvalidOperation
from django.core.exceptions import ValidationError
from django.db import transaction

from orders.models import OrderItemAthlete, OrderItemMeasurement
from orders.services.validators import OrderAthleteValidator
from teams.models import UserTeamMembership


class OrderItemAthleteService:

    # =========================================================
    # ADD ATHLETE
    # =========================================================
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

    # =========================================================
    # IMPORT FROM TEAM (CORE FLOW)
    # =========================================================

    @staticmethod
    @transaction.atomic
    def import_from_team(order_item):

        # 🔒 LOCK para evitar race conditions
        order_item = (
            order_item.__class__.objects.select_for_update()
            .select_related("order", "product")
            .get(pk=order_item.pk)
        )

        order = order_item.order
        product = order_item.product

        # -------------------------
        # VALIDACIONES
        # -------------------------
        if not order.can_edit_general():
            raise ValidationError("La orden no es editable.")

        if order.order_type != "TEAM":
            raise ValidationError("Solo órdenes TEAM permiten importar atletas.")

        if not product.requires_athletes:
            raise ValidationError("Este producto no usa atletas.")

        if not order.owner_team:
            raise ValidationError("La orden no tiene equipo asignado.")

        # -------------------------
        # QUERY
        # -------------------------
        memberships = (
            UserTeamMembership.objects.filter(
                team=order.owner_team,
                status="accepted",
                is_active=True,
                role_in_team="ATLETA",
            )
            .select_related("user")
            .prefetch_related("user__measurements")
        )

        existing_athletes = {
            ai.athlete_id: ai
            for ai in order_item.athletes.all().prefetch_related("measurements")
        }

        created = 0
        updated = 0
        errors = []

        valid_athlete_ids = []

        # -------------------------
        # LOOP PRINCIPAL
        # -------------------------
        for membership in memberships:
            athlete = membership.user
            valid_athlete_ids.append(athlete.id)

            try:
                if athlete.id not in existing_athletes:
                    OrderItemAthleteService.add_athlete(order_item, athlete)
                    created += 1
                else:
                    athlete_item = existing_athletes[athlete.id]
                    OrderItemAthleteService.sync_measurements_from_athlete(athlete_item)
                    updated += 1

            except ValidationError as e:
                errors.append(f"{athlete}: {', '.join(e.messages)}")

        # -------------------------
        # LIMPIEZA DE ATLETAS OBSOLETOS
        # -------------------------
        OrderItemAthleteService._remove_stale_athletes(
            order_item, valid_athlete_ids, existing_athletes
        )

        return {
            "created": created,
            "updated": updated,
            "errors": errors,
        }

    # =========================================================
    # REMOVE STALE ATHLETES
    # =========================================================
    @staticmethod
    def _remove_stale_athletes(order_item, valid_athlete_ids, existing_athletes):
        """
        Elimina atletas que ya no pertenecen al equipo.
        Optimizado usando sets.
        """
        existing_ids = set(existing_athletes.keys())
        valid_ids = set(valid_athlete_ids)

        to_delete = existing_ids - valid_ids

        if to_delete:
            order_item.athletes.filter(athlete_id__in=to_delete).delete()

    # =========================================================
    # CREATE SNAPSHOT
    # =========================================================
    @staticmethod
    def _create_measurement_snapshot(athlete_item):
        product = athlete_item.order_item.product
        athlete = athlete_item.athlete

        athlete_measurements = {m.field_id: m.value for m in athlete.measurements.all()}

        snapshots = []

        for pmf in product.measurement_fields.select_related("field").all():
            field = pmf.field

            raw_value = athlete_measurements.get(pmf.field_id)
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
                update_fields=["value_original", "value"],
            )

    # =========================================================
    # SYNC MEASUREMENTS
    # =========================================================
    @staticmethod
    @transaction.atomic
    def sync_measurements_from_athlete(athlete_item):

        athlete = athlete_item.athlete
        product = athlete_item.order_item.product

        athlete_measurements = {m.field_id: m.value for m in athlete.measurements.all()}

        existing_measurements = {m.field_id: m for m in athlete_item.measurements.all()}

        product_fields = list(product.measurement_fields.select_related("field").all())

        updates = []
        new_snapshots = []

        for pmf in product_fields:
            field_id = pmf.field_id
            field = pmf.field

            profile_value = athlete_measurements.get(field_id, "")

            if field_id in existing_measurements:
                measurement = existing_measurements[field_id]

                if measurement.is_modified:
                    continue

                if measurement.value != profile_value:
                    measurement.value = profile_value
                    measurement.value_original = profile_value
                    updates.append(measurement)

            else:
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

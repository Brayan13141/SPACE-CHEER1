"""Traduce un roster {alumno: talla} a OrderItems, uno por talla.

La talla de un alumno dentro de un pedido ES el size_variant del OrderItem
donde vive su fila OrderItemAthlete. Por eso este servicio nunca toca
size_variant de un item: mover a alguien de M a L es borrar su fila en un item
y crearla en el otro.
"""

from dataclasses import dataclass, field as dataclass_field

from django.core.exceptions import ValidationError
from django.db import transaction

from orders.models import OrderItem, OrderItemAthlete


@dataclass
class SizeAssignmentResult:
    ok: bool
    errors: dict = dataclass_field(default_factory=dict)   # {athlete_id: mensaje}
    changed_athletes: list = dataclass_field(default_factory=list)


class OrderItemSizeAssignmentService:

    @staticmethod
    def applies_to(product):
        return (
            product.usage_type == "TEAM_CUSTOM"
            and product.size_strategy == "STANDARD"
        )

    @staticmethod
    @transaction.atomic
    def reconcile(order, product, assignments, viewer):
        """assignments: {athlete_id: talla}. Talla vacia = sin asignar."""
        if not OrderItemSizeAssignmentService.applies_to(product):
            raise ValidationError("Este producto no usa tallas por alumno")

        if order.order_type != "TEAM":
            raise ValidationError("Solo las ordenes de equipo usan roster de tallas")

        if not order.can_edit_general():
            raise ValidationError("La orden no es editable")

        # Lock: dos coaches del mismo equipo capturando a la vez es real.
        items = {
            item.size_variant.size: item
            for item in OrderItem.objects.select_for_update()
            .filter(order=order, product=product, size_variant__isnull=False)
            .select_related("size_variant")
        }

        variants = {v.size: v for v in product.size_variants.all()}
        valid_athlete_ids = OrderItemSizeAssignmentService._team_athlete_ids(order)

        errors = {}
        targets = {}     # {size: [athlete_id]}

        for athlete_id, raw_size in assignments.items():
            size = (raw_size or "").strip().upper()

            if athlete_id not in valid_athlete_ids:
                errors[athlete_id] = "Ya no es atleta activo del equipo."
                continue

            if not size:
                continue     # sin talla: no se asigna, y se le quita la fila vieja

            if size not in variants:
                errors[athlete_id] = (
                    f"La talla {size} no está disponible en este producto."
                )
                continue

            targets.setdefault(size, []).append(athlete_id)

        assigned_ids = {aid for ids in targets.values() for aid in ids}
        changed = []

        # 1. Quitar filas que ya no corresponden (cambio de talla, vaciado, baja).
        for size, item in items.items():
            keep = set(targets.get(size, []))
            stale = item.athletes.exclude(athlete_id__in=keep)
            for athlete_item in stale.select_related("athlete"):
                changed.append(athlete_item.athlete)
            stale.delete()

        # 2. Crear los items que falten y las filas nuevas.
        for size, athlete_ids in targets.items():
            item = items.get(size)
            if item is None:
                item = OrderItem.objects.create(
                    order=order,
                    product=product,
                    quantity=len(athlete_ids),
                    size_variant=variants[size],
                )
                items[size] = item

            existing = set(item.athletes.values_list("athlete_id", flat=True))
            for athlete_id in athlete_ids:
                if athlete_id in existing:
                    continue
                athlete_item = OrderItemAthlete.objects.create(
                    order_item=item, athlete_id=athlete_id
                )
                changed.append(athlete_item.athlete)

        # 3. La cantidad la manda el roster (Decision 4).
        for size, item in list(items.items()):
            count = item.athletes.count()
            if count == 0:
                item.delete()
                del items[size]
                continue
            if item.quantity != count:
                item.quantity = count
                item.save()

        order.invalidate_cache()

        return SizeAssignmentResult(
            ok=not errors,
            errors=errors,
            changed_athletes=changed,
        )

    @staticmethod
    def _team_athlete_ids(order):
        from teams.models import UserTeamMembership

        return set(
            UserTeamMembership.objects.filter(
                team=order.owner_team,
                status="accepted",
                is_active=True,
                role_in_team="ATHLETE",
            ).values_list("user_id", flat=True)
        )

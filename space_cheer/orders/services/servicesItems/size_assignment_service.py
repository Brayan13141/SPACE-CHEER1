"""Traduce un roster {alumno: talla} a OrderItems, uno por talla.

La talla de un alumno dentro de un pedido ES el size_variant del OrderItem
donde vive su fila OrderItemAthlete. Por eso este servicio nunca toca
size_variant de un item: mover a alguien de M a L es borrar su fila en un item
y crearla en el otro.
"""

from dataclasses import dataclass, field as dataclass_field

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q

from orders.models import Order, OrderItem, OrderItemAthlete
from orders.services.servicesItems.product_selector import (
    available_products_for_order,
)


@dataclass
class SizeAssignmentResult:
    ok: bool
    errors: dict = dataclass_field(default_factory=dict)   # {athlete_id: mensaje}
    changed_athletes: list = dataclass_field(default_factory=list)
    profile_updates: list = dataclass_field(default_factory=list)


class OrderItemSizeAssignmentService:

    @staticmethod
    def applies_to(product):
        return product.uses_standard_sizes

    @staticmethod
    @transaction.atomic
    def reconcile(order, product, assignments, viewer):
        """assignments: {athlete_id: talla}. Talla vacia = sin asignar.

        assignments ES EL ALCANCE de la operacion, no solo su contenido: quien
        llama manda las filas sobre las que tiene autoridad, y este servicio no
        toca ninguna otra. La vista se lo pasa ya filtrado por permisos
        (SizeGridService.assignments_from_post devuelve solo las filas
        editables), asi que un tutor manda UNA fila y el resto del equipo no es
        asunto suyo. Conciliar contra el estado completo con un roster parcial
        borraba las filas de los demas, sus items y las cantidades del pedido.
        """
        if not OrderItemSizeAssignmentService.applies_to(product):
            raise ValidationError("Este producto no usa tallas por alumno")

        if order.order_type != "TEAM":
            raise ValidationError("Solo las ordenes de equipo usan roster de tallas")

        # La orden viene autorizada por quien llama; el PRODUCTO no. Sin esto,
        # el OrderItem.objects.create() de mas abajo se salta el filtro de
        # catalogo que si aplica OrderItemService.add_product, y OrderItem.clean()
        # no lo cubre (solo frena los TEAM_ONLY de otro equipo). Va aqui y no en
        # la vista para cubrir cualquier llamada futura al servicio.
        if not available_products_for_order(order).filter(pk=product.pk).exists():
            raise ValidationError("Este producto no está permitido para esta orden")

        # Lock a nivel de la ORDEN, no de los items: select_for_update sobre los
        # items existentes no puede bloquear una fila que todavia no existe, asi
        # que dos coaches creando la misma talla por primera vez creaban DOS
        # OrderItem para (order, product, size_variant) y partian la cantidad en
        # silencio. Serializar por orden cierra ese hueco sin migracion; un
        # UniqueConstraint exigiria una y ademas no aplicaria a size_variant NULL.
        locked_order = Order.objects.select_for_update().get(pk=order.pk)

        # La editabilidad se comprueba DESPUES del lock y sobre la fila recien
        # leida. Sobre `order` se leia el estado que la vista trajo en el GET:
        # entre esa lectura y este punto la orden pudo cerrarse o pasar a
        # produccion, y el guardado entraba igual.
        if not locked_order.can_edit_general():
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

        changed = []

        # 1. Quitar filas que ya no corresponden (cambio de talla, vaciado, baja).
        #    Solo dentro del alcance de quien guarda; la unica excepcion es la
        #    fila de alguien que ya no es atleta activo, que no puede ser valida
        #    para nadie y por eso se retira aunque no venga en este roster.
        scope_ids = set(assignments)
        for size, item in items.items():
            keep = set(targets.get(size, []))
            stale = item.athletes.exclude(athlete_id__in=keep).filter(
                Q(athlete_id__in=scope_ids) | ~Q(athlete_id__in=valid_athlete_ids)
            )
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

        profile_updates = OrderItemSizeAssignmentService._sync_profile_sizes(
            targets, viewer
        )

        order.invalidate_cache()

        return SizeAssignmentResult(
            ok=not errors,
            errors=errors,
            changed_athletes=changed,
            profile_updates=profile_updates,
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

    @staticmethod
    def _sync_profile_sizes(targets, viewer):
        """La talla capturada en el pedido actualiza la del alumno (Decision 5).

        Solo si cambio: un guardado que no mueve la talla no debe tocar
        updated_at ni dejar auditoria, o la bitacora se llena de ruido y deja
        de servir para investigar.
        """
        from django.utils import timezone

        from measures.models import AthleteStandardSize

        valid_sizes = {code for code, _ in AthleteStandardSize.SIZE_CHOICES}

        deseado = {}
        for size, athlete_ids in targets.items():
            if size not in valid_sizes:
                # El producto ofrece una talla fuera de la escala del alumno
                # (p. ej. calzado numerico): no se adivina nada.
                continue
            for athlete_id in athlete_ids:
                deseado[athlete_id] = size

        if not deseado:
            return []

        # Una sola lectura para todo el roster. Antes era un SELECT mas un
        # update_or_create POR ALUMNO (~3 consultas cada uno) para escribir una
        # talla que en la mayoria de los guardados no cambia.
        actuales = {
            fila.user_id: fila
            for fila in AthleteStandardSize.objects.filter(user_id__in=deseado)
        }

        ahora = timezone.now()
        nuevas = []
        cambiadas = []
        updated = []

        for athlete_id, size in deseado.items():
            fila = actuales.get(athlete_id)

            if fila is None:
                nuevas.append(
                    AthleteStandardSize(
                        user_id=athlete_id, size=size, updated_by=viewer
                    )
                )
            elif fila.size != size:
                fila.size = size
                fila.updated_by = viewer
                # bulk_update NO dispara auto_now, asi que updated_at se
                # quedaria con la fecha vieja y el dato dejaria de ser
                # auditable. Se pone a mano y se incluye en los campos.
                fila.updated_at = ahora
                cambiadas.append(fila)
            else:
                continue     # sin cambio: no se toca updated_at ni la bitacora

            updated.append(athlete_id)

        if nuevas:
            AthleteStandardSize.objects.bulk_create(nuevas)
        if cambiadas:
            AthleteStandardSize.objects.bulk_update(
                cambiadas, ["size", "updated_by", "updated_at"]
            )

        return updated

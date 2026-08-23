"""Agrupa por PRODUCTO los items que llevan talla por alumno.

Un pedido de 12 playeras son 3 OrderItem (uno por talla), y cada uno es una
fila mas en la pantalla: sin agrupar, el mismo producto aparece tres veces y el
boton "capturar tallas" tambien, aunque los tres lleven al mismo roster.

Cada fila carga ademas lo que antes solo vivia en el OrderItem (id, precio y
alumnos), porque el detalle del pedido pinta una tabla
Talla/Cant/Unit/Subtotal/Atletas y una papelera por talla: sin esto habria que
volver a recorrer order.items en la plantilla y el producto seguiria saliendo
dos veces.
"""

from dataclasses import dataclass, field as dataclass_field
from decimal import Decimal

from orders.services.sizes.ordering import size_sort_key


@dataclass
class SizeGroupRow:
    """Una talla del producto: el OrderItem que la representa.

    `quantity` y `assigned` NO son lo mismo y pueden separarse: reconcile() los
    mantiene iguales, pero OrderItemService.add_product crea el item con una
    cantidad a mano y sin atletas. `quantity` es lo que se cobra y lo que hay
    que cortar; `assigned` es a cuantos alumnos se les reparte.
    """

    size: str
    quantity: int
    assigned: int
    item_id: int
    unit_price: Decimal
    subtotal: Decimal
    athlete_names: list = dataclass_field(default_factory=list)
    athlete_ids: list = dataclass_field(default_factory=list)

    @property
    def sin_repartir(self):
        """Piezas cobradas que no tienen alumno. Cero es lo normal."""
        return max(self.quantity - self.assigned, 0)


@dataclass
class SizeGroup:
    product: object
    rows: list = dataclass_field(default_factory=list)   # [SizeGroupRow]
    assigned: int = 0
    total: int = 0
    # Quien del roster no tiene talla en ESTE producto. La hoja de produccion
    # los imprime marcados: un numero suelto no sirve para ir a buscarlos.
    unassigned_names: list = dataclass_field(default_factory=list)
    unassigned_ids: list = dataclass_field(default_factory=list)

    @property
    def missing(self):
        return max(self.total - self.assigned, 0)

    @property
    def quantity(self):
        """Piezas cobradas del producto. Es lo que se corta."""
        return sum(fila.quantity for fila in self.rows)

    @property
    def sin_repartir(self):
        return sum(fila.sin_repartir for fila in self.rows)

    @property
    def printed_user_ids(self):
        """Todos los alumnos que una pantalla de este grupo nombra.

        La hoja de produccion imprime tambien a los que NO tienen talla, asi
        que auditar solo los OrderItemAthlete deja fuera justo a los que salen
        marcados en papel.
        """
        return [
            athlete_id for fila in self.rows for athlete_id in fila.athlete_ids
        ] + list(self.unassigned_ids)

    @property
    def subtotal(self):
        return sum((fila.subtotal for fila in self.rows), Decimal("0"))

    @property
    def item_ids(self):
        """Los items que esta tarjeta ya representa.

        El detalle del pedido los salta en su bucle de productos; si no, cada
        talla vuelve a salir como una tarjeta suelta debajo del grupo.
        """
        return [fila.item_id for fila in self.rows]


class SizeSummaryService:

    @staticmethod
    def for_order(order):
        from teams.models import UserTeamMembership

        if order.order_type != "TEAM":
            # Misma guarda que SizeGridService.build() y reconcile(). Sin ella
            # el resumen sale con total=0 (owner_team es None, asi que el conteo
            # de membresias no encuentra a nadie) y la pantalla ofrece capturar
            # un roster que no existe.
            return []

        items = [
            item
            for item in order.items.select_related("product", "size_variant")
            .prefetch_related("athletes__athlete")
            .all()
            if item.product.uses_standard_sizes and item.size_variant_id
        ]
        if not items:
            return []

        # Se trae el roster entero y no solo su .count(): son los mismos datos
        # en la misma consulta, y con ellos se sabe QUIEN falta, no solo
        # cuantos.
        roster = [
            membresia.user
            for membresia in UserTeamMembership.objects.filter(
                team=order.owner_team,
                status="accepted",
                is_active=True,
                role_in_team="ATHLETE",
            ).select_related("user")
        ]
        total = len(roster)

        grupos = {}
        con_talla = {}
        for item in items:
            grupo = grupos.setdefault(
                item.product_id, SizeGroup(product=item.product, total=total)
            )
            # El prefetch ya trajo a los atletas: item.athletes.count() dispara
            # una consulta por talla y len() de la lista cacheada no.
            asignaciones = list(item.athletes.all())
            con_talla.setdefault(item.product_id, set()).update(
                oia.athlete_id for oia in asignaciones
            )
            grupo.rows.append(
                SizeGroupRow(
                    size=item.size_variant.size,
                    quantity=item.quantity,
                    assigned=len(asignaciones),
                    item_id=item.id,
                    unit_price=item.unit_price,
                    subtotal=item.subtotal,
                    athlete_names=[
                        oia.athlete.get_full_name() or oia.athlete.email
                        for oia in asignaciones
                    ],
                    athlete_ids=[oia.athlete_id for oia in asignaciones],
                )
            )
            grupo.assigned += len(asignaciones)

        # Por la escala del alumno, no por cantidad. El orden viejo ("mas
        # alumnos primero") servia para una tira de badges donde se busca la
        # talla dominante; estas filas se leen al reves, buscando UNA talla
        # concreta, y XS, S, M, L, XL, XXL es como esta escrita la etiqueta.
        for product_id, grupo in grupos.items():
            grupo.rows.sort(key=lambda fila: size_sort_key(fila.size))
            asignados = con_talla.get(product_id, set())
            sin_talla = [
                alumno for alumno in roster if alumno.id not in asignados
            ]
            grupo.unassigned_names = [
                alumno.get_full_name() or alumno.email for alumno in sin_talla
            ]
            grupo.unassigned_ids = [alumno.id for alumno in sin_talla]

        return list(grupos.values())

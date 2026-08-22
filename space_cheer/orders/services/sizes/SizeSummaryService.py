"""Agrupa por PRODUCTO los items que llevan talla por alumno.

Un pedido de 12 playeras son 3 OrderItem (uno por talla), y cada uno es una
fila mas en la pantalla: sin agrupar, el mismo producto aparece tres veces y el
boton "capturar tallas" tambien, aunque los tres lleven al mismo roster.
"""

from dataclasses import dataclass, field as dataclass_field


@dataclass
class SizeGroup:
    product: object
    rows: list = dataclass_field(default_factory=list)   # [(talla, alumnos)]
    assigned: int = 0
    total: int = 0

    @property
    def missing(self):
        return max(self.total - self.assigned, 0)


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
            for item in order.items.select_related("product", "size_variant").all()
            if item.product.uses_standard_sizes and item.size_variant_id
        ]
        if not items:
            return []

        total = UserTeamMembership.objects.filter(
            team=order.owner_team,
            status="accepted",
            is_active=True,
            role_in_team="ATHLETE",
        ).count()

        grupos = {}
        for item in items:
            grupo = grupos.setdefault(
                item.product_id, SizeGroup(product=item.product, total=total)
            )
            asignados = item.athletes.count()
            grupo.rows.append((item.size_variant.size, asignados))
            grupo.assigned += asignados

        # Mas alumnos primero: la talla del grueso del equipo es la que se mira.
        for grupo in grupos.values():
            grupo.rows.sort(key=lambda fila: (-fila[1], fila[0]))

        return list(grupos.values())

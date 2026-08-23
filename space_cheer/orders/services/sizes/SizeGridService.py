"""Arma la matriz de tallas: filas = alumnos del EQUIPO, columna = talla.

Diferencia estructural con MeasurementGridService: alli las filas son
OrderItemAthlete que YA existen; aqui las filas son los alumnos del equipo,
tengan fila o no — asignarlos es justamente el punto de la pantalla.
"""

from dataclasses import dataclass, field as dataclass_field

from django.core.exceptions import PermissionDenied


@dataclass
class SizeGridRow:
    athlete_id: int
    athlete_name: str
    athlete: object
    size: str = ""
    editable: bool = False
    input_name: str = ""
    error: str = ""


@dataclass
class SizeGrid:
    order: object
    product: object
    sizes: list = dataclass_field(default_factory=list)
    rows: list = dataclass_field(default_factory=list)
    can_edit: bool = False
    # can_edit es False por dos motivos distintos: la orden no admite ediciones
    # (is_locked=True), o este viewer no tiene filas escribibles. Decirle
    # "bloqueado" al segundo seria mentirle.
    is_locked: bool = False
    assigned_count: int = 0
    total_count: int = 0


class SizeGridService:

    LOCKED_MESSAGE = "Las tallas están cerradas para esta orden."
    # Dos causas distintas, dos mensajes: ver el roster sin poder capturarlo no
    # es lo mismo que una orden bloqueada (ver el comentario de SizeGrid.can_edit).
    NO_WRITE_MESSAGE = "No tienes permiso para capturar las tallas de esta orden."

    @staticmethod
    def build(order, product, viewer, values=None, errors=None):
        from measures.models import AthleteStandardSize
        from orders.models import OrderItemAthlete
        from orders.services.servicesItems.product_selector import (
            available_products_for_order,
        )
        from orders.services.servicesItems.size_assignment_service import (
            OrderItemSizeAssignmentService,
        )

        values = values or {}
        errors = errors or {}

        if not OrderItemSizeAssignmentService.applies_to(product):
            raise PermissionDenied

        if order.order_type != "TEAM":
            # Espeja la guarda de reconcile(). Sin esto, _team_athletes() filtra
            # por team=None, devuelve [] y la pantalla sale VACIA en vez de
            # fallar: parece que el equipo no tiene alumnos.
            raise PermissionDenied

        # Misma guarda que reconcile(): si el producto no se puede pedir en esta
        # orden, la pantalla no se ofrece.
        if not available_products_for_order(order).filter(pk=product.pk).exists():
            raise PermissionDenied

        sizes = SizeGridService._ordered_sizes(product)

        athletes = SizeGridService._team_athletes(order)
        sees_all = SizeGridService._sees_every_row(order, viewer)

        ward_ids = set()

        if not sees_all:
            # Dos alcances distintos, no uno: el tutor ESCRIBE las filas de sus
            # menores; el alumno solo LEE la suya, que es un dato de el. Antes
            # el alumno era el unico del equipo que no podia ver su propia
            # talla: caia en el PermissionDenied de abajo.
            wards = [
                athlete
                for athlete in athletes
                if SizeGridService._is_guardian_of(viewer, athlete)
            ]
            ward_ids = {athlete.id for athlete in wards}
            own = [
                athlete
                for athlete in athletes
                if athlete.id == viewer.id and athlete.id not in ward_ids
            ]
            athletes = wards + own
            if not athletes:
                raise PermissionDenied

        # Talla ya asignada en el pedido: el item donde vive su fila.
        assigned = dict(
            OrderItemAthlete.objects.filter(
                order_item__order=order, order_item__product=product
            ).values_list("athlete_id", "order_item__size_variant__size")
        )

        profile_sizes = dict(
            AthleteStandardSize.objects.filter(
                user__in=athletes
            ).values_list("user_id", "size")
        )

        is_locked = SizeGridService._order_blocks_editing(order)

        # Escribible se decide POR FILA: un tutor que ademas es atleta del
        # equipo escribe las de sus menores y no la suya.
        if is_locked:
            writable_ids = set()
        elif sees_all:
            writable_ids = (
                {athlete.id for athlete in athletes}
                if (
                    viewer.is_superuser
                    or order.created_by_id == viewer.id
                    or SizeGridService._has_admin_role(viewer)
                )
                else set()
            )
        else:
            writable_ids = ward_ids

        rows = []
        for athlete in athletes:
            input_name = f"size_{athlete.id}"

            if input_name in values:
                size = (values.get(input_name) or "").strip().upper()
            else:
                size = assigned.get(athlete.id) or profile_sizes.get(athlete.id, "")
                # No se adivina: una talla que el producto no ofrece se muestra
                # vacia y el coach la captura a mano.
                if size not in sizes:
                    size = ""

            rows.append(
                SizeGridRow(
                    athlete_id=athlete.id,
                    athlete_name=athlete.get_full_name() or athlete.username,
                    athlete=athlete,
                    size=size,
                    editable=athlete.id in writable_ids,
                    input_name=input_name,
                    error=errors.get(athlete.id, ""),
                )
            )

        rows.sort(key=lambda r: (r.athlete_name.lower(), r.athlete_id))

        return SizeGrid(
            order=order,
            product=product,
            sizes=sizes,
            rows=rows,
            can_edit=any(row.editable for row in rows),
            is_locked=is_locked,
            assigned_count=sum(1 for row in rows if row.size),
            total_count=len(rows),
        )

    @staticmethod
    def assignments_from_post(grid, post_data):
        """SEGURIDAD: itera sobre las filas editables del grid, NUNCA sobre las
        claves de post_data. Una celda ajena posteada a mano no se lee."""
        return {
            row.athlete_id: (post_data.get(row.input_name) or "").strip().upper()
            for row in grid.rows
            if row.editable
        }

    @staticmethod
    def _team_athletes(order):
        from teams.models import UserTeamMembership

        return [
            membership.user
            for membership in UserTeamMembership.objects.filter(
                team=order.owner_team,
                status="accepted",
                is_active=True,
                role_in_team="ATHLETE",
            ).select_related("user", "user__athleteprofile")
        ]

    @staticmethod
    def _ordered_sizes(product):
        """La escala del alumno manda el orden, no el alfabeto.

        order_by("size") devolvia L, M, S, XL, XS, XXL, que no es el orden de
        ninguna etiqueta de ropa. Una talla fuera de la escala (calzado
        numerico, por ejemplo) va al final en vez de inventarle una posicion.
        """
        from orders.services.sizes.ordering import size_sort_key

        return sorted(
            product.size_variants.values_list("size", flat=True),
            key=size_sort_key,
        )

    @staticmethod
    def _sees_every_row(order, viewer):
        from orders.models import Order

        return (
            Order.objects.visible_for_user(viewer).filter(pk=order.pk).exists()
        )

    @staticmethod
    def _has_admin_role(viewer):
        return viewer.roles.filter(name="ADMIN").exists()

    @staticmethod
    def _is_guardian_of(viewer, athlete):
        # Mismo criterio que MeasurementGridService._is_guardian_of, pero sobre
        # un User en vez de un OrderItemAthlete: aqui las filas son alumnos del
        # equipo, no filas del pedido. Unificar las tres variantes que ya
        # existen (esta, la del grid de medidas y
        # AccountPermissions._is_guardian_of) es un refactor aparte.
        from accounts.models import AthleteProfile

        try:
            profile = athlete.athleteprofile
        except AthleteProfile.DoesNotExist:
            return False
        return profile.guardian_id == viewer.id and athlete.is_minor

    @staticmethod
    def _order_blocks_editing(order):
        return not (order.can_edit_general() and order.can_edit_measurements())

"""Arma la matriz de medidas de un OrderItem: filas = atletas, columnas = campos.

Es el único componente que decide qué celda ve y escribe cada viewer.
Vistas y templates solo consumen el resultado.
"""

from dataclasses import dataclass, field as dataclass_field

from django.core.exceptions import PermissionDenied


@dataclass(frozen=True)
class GridCell:
    field_id: int
    field_name: str
    field_unit: str
    required: bool
    value: str
    is_modified: bool
    editable: bool
    input_name: str
    error: str = ""

    @property
    def has_value(self) -> bool:
        return bool(self.value and self.value.strip())

    @property
    def display_value(self) -> str:
        """Nunca muestra None ni cadena vacía: una medida ausente es '—'."""
        if not self.has_value:
            return "—"
        unit = f" {self.field_unit}" if self.field_unit else ""
        return f"{self.value}{unit}"


@dataclass
class GridRow:
    athlete_item_id: int
    athlete_name: str
    cells: list = dataclass_field(default_factory=list)
    is_complete: bool = False


@dataclass
class MeasurementGrid:
    item: object
    columns: list = dataclass_field(default_factory=list)
    rows: list = dataclass_field(default_factory=list)
    can_edit: bool = False
    complete_count: int = 0
    total_count: int = 0


class MeasurementGridService:

    @staticmethod
    def columns_for(product):
        """Campos del producto en orden determinista.

        ProductMeasurementField no define Meta.ordering, así que sin este
        order_by explícito las columnas salen en orden arbitrario y pueden
        cambiar entre recargas.
        """
        return list(
            product.measurement_fields.select_related("field").order_by(
                "field__order", "field__name", "field_id"
            )
        )

    @staticmethod
    def athlete_items_for(item):
        return list(
            item.athletes.select_related("athlete")
            .prefetch_related("measurements")
            .order_by("athlete__first_name", "athlete__last_name", "id")
        )

    @staticmethod
    def build(item, viewer, values=None, errors=None):
        values = values or {}
        errors = errors or {}

        columns = MeasurementGridService.columns_for(item.product)
        athlete_items = MeasurementGridService.visible_athlete_items(item, viewer)
        editable_ids = MeasurementGridService.editable_athlete_item_ids(
            item, viewer, athlete_items
        )

        rows = []
        for athlete_item in athlete_items:
            existing = {m.field_id: m for m in athlete_item.measurements.all()}
            cells = []
            for product_field in columns:
                field_id = product_field.field_id
                input_name = f"m-{athlete_item.id}-{field_id}"
                stored = existing.get(field_id)

                if input_name in values:
                    value = values[input_name]
                else:
                    value = stored.value if stored else ""

                cells.append(
                    GridCell(
                        field_id=field_id,
                        field_name=product_field.field.name,
                        field_unit=product_field.field.unit,
                        required=product_field.required,
                        value=value,
                        is_modified=bool(stored and stored.is_modified),
                        editable=athlete_item.id in editable_ids,
                        input_name=input_name,
                        error=errors.get(input_name, ""),
                    )
                )

            rows.append(
                GridRow(
                    athlete_item_id=athlete_item.id,
                    athlete_name=(
                        athlete_item.athlete.get_full_name()
                        or athlete_item.athlete.email
                    ),
                    cells=cells,
                    is_complete=MeasurementGridService._row_is_complete(
                        columns, cells
                    ),
                )
            )

        return MeasurementGrid(
            item=item,
            columns=columns,
            rows=rows,
            can_edit=bool(editable_ids),
            complete_count=sum(1 for row in rows if row.is_complete),
            total_count=len(rows),
        )

    @staticmethod
    def _row_is_complete(columns, cells):
        """Misma semántica que OrderItemAthlete.has_complete_measurements(),
        pero en memoria: recorrer el modelo por atleta sería N+1.

        Un producto MEASUREMENTS sin campos configurados está mal configurado
        y NO cuenta como completo (evita el badge 'Completo' vacío).
        """
        if not columns:
            return False
        return all(cell.has_value for cell in cells if cell.required)

    @staticmethod
    def _is_guardian_of(viewer, athlete_item):
        from accounts.models import AthleteProfile

        try:
            profile = athlete_item.athlete.athleteprofile
        except AthleteProfile.DoesNotExist:
            return False
        return profile.guardian_id == viewer.id and athlete_item.athlete.is_minor

    @staticmethod
    def _is_assigned_operario(item, viewer):
        # Import local: production importa orders, un import a nivel de módulo
        # en sentido contrario cerraría el ciclo.
        from production.models import ProductionTask

        return ProductionTask.objects.filter(
            order_item=item,
            assigned_to=viewer,
            stage__productionrole__operarioroleassignment__user=viewer,
        ).exists()

    @staticmethod
    def _sees_every_row(item, viewer):
        from orders.models import Order

        if Order.objects.visible_for_user(viewer).filter(pk=item.order_id).exists():
            return True
        return MeasurementGridService._is_assigned_operario(item, viewer)

    @staticmethod
    def visible_athlete_items(item, viewer):
        """Filas que este viewer puede ver. PermissionDenied si no puede ver ninguna."""
        athlete_items = MeasurementGridService.athlete_items_for(item)

        if MeasurementGridService._sees_every_row(item, viewer):
            return athlete_items

        own = [
            athlete_item
            for athlete_item in athlete_items
            if MeasurementGridService._is_guardian_of(viewer, athlete_item)
        ]
        if own:
            return own

        raise PermissionDenied

    @staticmethod
    def editable_athlete_item_ids(item, viewer, athlete_items):
        """Ids de filas que este viewer puede ESCRIBIR.

        El operario nunca cae en ninguna rama: no es creador, no es ADMIN y no
        es guardián, así que recibe el conjunto vacío.
        """
        order = item.order
        if not (order.can_edit_general() and order.can_edit_measurements()):
            return set()

        is_privileged = (
            viewer.is_superuser
            or order.created_by_id == viewer.id
            or viewer.roles.filter(name="ADMIN").exists()
        )
        if is_privileged:
            return {athlete_item.id for athlete_item in athlete_items}

        return {
            athlete_item.id
            for athlete_item in athlete_items
            if MeasurementGridService._is_guardian_of(viewer, athlete_item)
        }
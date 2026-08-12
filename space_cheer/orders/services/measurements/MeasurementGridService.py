"""Arma la matriz de medidas de un OrderItem: filas = atletas, columnas = campos.

Es el único componente que decide qué celda ve y escribe cada viewer.
Vistas y templates solo consumen el resultado.
"""

from dataclasses import dataclass, field as dataclass_field

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction


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
    # Instancia User de la fila: evita que las vistas vuelvan a la base de
    # datos por cada atleta para registrar el acceso PII.
    athlete: object = None
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


@dataclass
class SaveResult:
    ok: bool
    errors: dict = dataclass_field(default_factory=dict)
    changed_athlete_items: list = dataclass_field(default_factory=list)


class MeasurementGridService:

    # Espeja OrderItemMeasurement.value = CharField(max_length=50).
    MAX_VALUE_LENGTH = 50

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
        # athlete__athleteprofile es obligatorio: _is_guardian_of() lo consulta
        # por fila, y sin el select_related el conteo crece con los atletas.
        return list(
            item.athletes.select_related("athlete", "athlete__athleteprofile")
            .prefetch_related("measurements")
            .order_by("athlete__first_name", "athlete__last_name", "id")
        )

    @staticmethod
    def build(item, viewer, values=None, errors=None, only_athlete_item_id=None):
        """Arma el grid del item.

        only_athlete_item_id restringe el grid a una sola fila. Lo usa la
        pagina "Medidas de <atleta>", cuyo titulo habla de un alumno: sin esto
        renderiaba a todo el equipo y solo auditaba a uno.
        """
        values = values or {}
        errors = errors or {}

        columns = MeasurementGridService.columns_for(item.product)
        athlete_items = MeasurementGridService.visible_athlete_items(item, viewer)

        if only_athlete_item_id is not None:
            athlete_items = [
                athlete_item
                for athlete_item in athlete_items
                if athlete_item.id == only_athlete_item_id
            ]
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
                    athlete=athlete_item.athlete,
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

    @staticmethod
    def save(item, viewer, post_data):
        """Guarda las celdas posteadas que el viewer tiene derecho a escribir.

        SEGURIDAD: se itera sobre las filas editables calculadas desde cero,
        nunca sobre las claves de post_data. Una celda ajena posteada a mano
        simplemente nunca se lee.
        """
        athlete_items = MeasurementGridService.visible_athlete_items(item, viewer)
        editable_ids = MeasurementGridService.editable_athlete_item_ids(
            item, viewer, athlete_items
        )
        if not editable_ids:
            raise PermissionDenied("No puedes editar estas medidas.")

        columns = MeasurementGridService.columns_for(item.product)

        # ── Paso 1: validar TODO antes de tocar la base de datos ───────────
        submitted = {}
        errors = {}
        for athlete_item in athlete_items:
            if athlete_item.id not in editable_ids:
                continue
            for product_field in columns:
                input_name = f"m-{athlete_item.id}-{product_field.field_id}"
                if input_name not in post_data:
                    continue
                value = (post_data.get(input_name) or "").strip()
                if product_field.required and not value:
                    errors[input_name] = (
                        f"'{product_field.field.name}' es obligatorio."
                    )
                elif len(value) > MeasurementGridService.MAX_VALUE_LENGTH:
                    # OrderItemMeasurement.value es CharField(max_length=50) y
                    # save() llama full_clean(): sin este chequeo, una celda
                    # larga revienta con ValidationError dentro del atomic y
                    # tumba el POST del roster entero con un 500.
                    errors[input_name] = (
                        f"'{product_field.field.name}': maximo "
                        f"{MeasurementGridService.MAX_VALUE_LENGTH} caracteres."
                    )
                submitted[(athlete_item.id, product_field.field_id)] = value

        if errors:
            return SaveResult(ok=False, errors=errors, changed_athlete_items=[])

        # ── Paso 2: guardar todo o nada ────────────────────────────────────
        # El try envuelve al atomic: OrderItemMeasurement.save() llama
        # full_clean(), asi que cualquier regla del modelo que el paso 1 no
        # anticipe (o un lock de medidas que entre en medio) llegaria como
        # ValidationError. Sin capturarla, el usuario pierde todo lo tecleado
        # con un 500 en vez de ver el error en su celda.
        changed = []
        try:
            with transaction.atomic():
                for athlete_item in athlete_items:
                    if athlete_item.id not in editable_ids:
                        continue

                    existing = {
                        m.field_id: m for m in athlete_item.measurements.all()
                    }
                    row_changed = False

                    for product_field in columns:
                        key = (athlete_item.id, product_field.field_id)
                        if key not in submitted:
                            continue
                        value = submitted[key]
                        measurement = existing.get(product_field.field_id)

                        if measurement:
                            if measurement.value != value:
                                measurement.value = value
                                measurement.save()
                                row_changed = True
                        elif value:
                            # Una celda vacía sin fila previa no crea registro:
                            # "" ya significa "sin medida".
                            athlete_item.measurements.create(
                                field_id=product_field.field_id,
                                field_name=product_field.field.name,
                                field_unit=product_field.field.unit,
                                value=value,
                            )
                            row_changed = True

                    if row_changed:
                        changed.append(athlete_item)
        except ValidationError as exc:
            return SaveResult(
                ok=False,
                errors={"__all__": "; ".join(exc.messages)},
                changed_athlete_items=[],
            )

        return SaveResult(ok=True, errors={}, changed_athlete_items=changed)
"""Arma la matriz de medidas de un OrderItem: filas = atletas, columnas = campos.

Es el único componente que decide qué celda ve y escribe cada viewer.
Vistas y templates solo consumen el resultado.
"""

import logging
from dataclasses import dataclass, field as dataclass_field

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GridColumn:
    field_id: int
    name: str
    unit: str
    required: bool
    # True si el campo YA NO pertenece al producto pero quedaron medidas
    # guardadas con el. Se muestra para no perder el dato de vista; nunca se
    # edita, porque OrderItemMeasurement.clean() rechaza los campos ajenos al
    # producto ("Campo no pertenece al producto").
    is_orphan: bool = False


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
    # `can_edit` es False por dos motivos MUY distintos: la orden no admite
    # ediciones, o este viewer no tiene filas escribibles. La pantalla decia
    # "cerradas o bloqueadas" en ambos casos, mintiendole al segundo.
    is_locked: bool = False
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

    LOCKED_MESSAGE = "Las medidas están cerradas o bloqueadas para esta orden."

    @staticmethod
    def _row_sort_key(athlete_item):
        athlete = athlete_item.athlete
        return (athlete.first_name or "", athlete.last_name or "", athlete_item.id)

    @staticmethod
    def columns_for(product):
        """Campos del producto en orden determinista.

        ProductMeasurementField no define Meta.ordering, así que sin este
        order_by explícito las columnas salen en orden arbitrario y pueden
        cambiar entre recargas.
        """
        return [
            GridColumn(
                field_id=product_field.field_id,
                name=product_field.field.name,
                unit=product_field.field.unit,
                required=product_field.required,
            )
            for product_field in product.measurement_fields.select_related(
                "field"
            ).order_by("field__order", "field__name", "field_id")
        ]

    @staticmethod
    def orphan_columns_for(athlete_items, product_field_ids):
        """Campos desligados del producto que todavía tienen medidas guardadas.

        Si un admin quita un campo del producto después de la captura, las
        filas de OrderItemMeasurement sobreviven. Mostrar solo las columnas del
        producto las hacía desaparecer de la pantalla del operario, que corta
        con ese dato en la mano.

        Se usan `field_name`/`field_unit` del propio registro: son el snapshot
        que ese modelo guarda justo para este caso.
        """
        orphans = {}
        for athlete_item in athlete_items:
            for measurement in athlete_item.measurements.all():
                if measurement.field_id in product_field_ids:
                    continue
                if not measurement.has_value:
                    continue
                orphans.setdefault(
                    measurement.field_id,
                    GridColumn(
                        field_id=measurement.field_id,
                        name=measurement.field_name,
                        unit=measurement.field_unit,
                        required=False,
                        is_orphan=True,
                    ),
                )
        return sorted(orphans.values(), key=lambda column: (column.name, column.field_id))

    @staticmethod
    def athlete_items_for(item):
        """Filas del item, ordenadas igual sin importar de dónde salgan.

        Si el llamador ya prefetcheó `athletes` -- el panel admin lo hace, con
        `measurements` adentro -- se reusa esa cache: armar aquí otra queryset
        ejecutaba el prefetch del llamador y lo tiraba a la basura, una vez por
        item. El orden se impone en Python para no depender del `order_by` que
        haya usado quien prefetcheó.

        CONTRATO para quien prefetchee `athletes`: incluir `measurements` y
        `select_related("athlete", "athlete__athleteprofile")`. Sin eso el grid
        vuelve a la base por cada fila y la optimización se da vuelta.
        """
        prefetched = getattr(item, "_prefetched_objects_cache", None) or {}
        if "athletes" in prefetched:
            return sorted(
                item.athletes.all(), key=MeasurementGridService._row_sort_key
            )

        # athlete__athleteprofile es obligatorio: _is_guardian_of() lo consulta
        # por fila, y sin el select_related el conteo crece con los atletas.
        return list(
            item.athletes.select_related("athlete", "athlete__athleteprofile")
            .prefetch_related("measurements")
            .order_by("athlete__first_name", "athlete__last_name", "id")
        )

    @staticmethod
    def build(
        item,
        viewer,
        values=None,
        errors=None,
        only_athlete_item_id=None,
        perm_cache=None,
    ):
        """Arma el grid del item.

        only_athlete_item_id restringe el grid a una sola fila. Lo usa la
        pagina "Medidas de <atleta>", cuyo titulo habla de un alumno: sin esto
        renderiaba a todo el equipo y solo auditaba a uno.

        perm_cache: dict compartido entre varias llamadas del MISMO request
        para no repetir las consultas de permisos (roles del viewer,
        visibilidad de la orden). Quien arma varios grids seguidos -- el panel
        admin, que hace uno por item -- debe pasar el mismo dict. Las claves
        incluyen el pk del viewer, asi que compartirlo entre usuarios no
        filtra permisos; aun asi no debe sobrevivir al request, porque un
        cambio de rol o de estado de la orden no lo invalida.
        """
        values = values or {}
        errors = errors or {}
        perm_cache = {} if perm_cache is None else perm_cache

        product_columns = MeasurementGridService.columns_for(item.product)
        athlete_items = MeasurementGridService.visible_athlete_items(
            item, viewer, perm_cache
        )

        if only_athlete_item_id is not None:
            athlete_items = [
                athlete_item
                for athlete_item in athlete_items
                if athlete_item.id == only_athlete_item_id
            ]
        editable_ids = MeasurementGridService.editable_athlete_item_ids(
            item, viewer, athlete_items, perm_cache
        )

        product_field_ids = {column.field_id for column in product_columns}
        columns = product_columns + MeasurementGridService.orphan_columns_for(
            athlete_items, product_field_ids
        )

        rows = []
        for athlete_item in athlete_items:
            existing = {m.field_id: m for m in athlete_item.measurements.all()}
            cells = []
            for column in columns:
                field_id = column.field_id
                input_name = f"m-{athlete_item.id}-{field_id}"
                stored = existing.get(field_id)

                if input_name in values:
                    value = values[input_name]
                else:
                    value = stored.value if stored else ""

                cells.append(
                    GridCell(
                        field_id=field_id,
                        field_name=column.name,
                        field_unit=column.unit,
                        required=column.required,
                        value=value,
                        is_modified=bool(stored and stored.is_modified),
                        editable=(
                            athlete_item.id in editable_ids and not column.is_orphan
                        ),
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
                    # product_columns, no columns: un producto sin campos
                    # configurados NO cuenta como completo, y las huerfanas no
                    # deben rescatarlo de esa regla.
                    is_complete=MeasurementGridService._row_is_complete(
                        product_columns, cells
                    ),
                )
            )

        return MeasurementGrid(
            item=item,
            columns=columns,
            rows=rows,
            can_edit=bool(editable_ids),
            is_locked=MeasurementGridService._order_blocks_editing(item.order),
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
    def _order_is_visible(item, viewer, perm_cache):
        """`visible_for_user()` para la orden del item, memoizado por orden.

        El panel admin arma un grid por cada item de la MISMA orden, y esta
        consulta incluye un `roles.filter(name="ADMIN")`: sin la memoización
        se repetía entera una vez por item.
        """
        from orders.models import Order

        # La clave incluye al viewer: un dict reusado entre usuarios (un
        # reporte por lotes, un comando de gestion) le entregaria a B los
        # permisos de A. El cache es una optimizacion, no una via de escalada.
        key = ("order_visible", viewer.pk, item.order_id)
        if key not in perm_cache:
            perm_cache[key] = (
                Order.objects.visible_for_user(viewer)
                .filter(pk=item.order_id)
                .exists()
            )
        return perm_cache[key]

    @staticmethod
    def _has_admin_role(viewer, perm_cache):
        key = ("admin_role", viewer.pk)
        if key not in perm_cache:
            perm_cache[key] = viewer.roles.filter(name="ADMIN").exists()
        return perm_cache[key]

    @staticmethod
    def _sees_every_row(item, viewer, perm_cache=None):
        perm_cache = {} if perm_cache is None else perm_cache

        if MeasurementGridService._order_is_visible(item, viewer, perm_cache):
            return True
        return MeasurementGridService._is_assigned_operario(item, viewer)

    @staticmethod
    def visible_athlete_items(item, viewer, perm_cache=None):
        """Filas que este viewer puede ver. PermissionDenied si no puede ver ninguna."""
        perm_cache = {} if perm_cache is None else perm_cache
        athlete_items = MeasurementGridService.athlete_items_for(item)

        if MeasurementGridService._sees_every_row(item, viewer, perm_cache):
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
    def _order_blocks_editing(order):
        """True si NINGUN usuario puede editar medidas, por estado de la orden.

        Es distinto de "este viewer no puede": lo primero es un estado que se
        comunica con un mensaje, lo segundo es un 403.
        """
        return not (order.can_edit_general() and order.can_edit_measurements())

    @staticmethod
    def editable_athlete_item_ids(item, viewer, athlete_items, perm_cache=None):
        """Ids de filas que este viewer puede ESCRIBIR.

        El operario nunca cae en ninguna rama: no es creador, no es ADMIN y no
        es guardián, así que recibe el conjunto vacío.
        """
        perm_cache = {} if perm_cache is None else perm_cache
        order = item.order
        if MeasurementGridService._order_blocks_editing(order):
            return set()

        is_privileged = (
            viewer.is_superuser
            or order.created_by_id == viewer.id
            or MeasurementGridService._has_admin_role(viewer, perm_cache)
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
        perm_cache = {}
        # El chequeo de visibilidad va PRIMERO: a quien no ve la orden no se le
        # confirma siquiera que existe o en que estado esta.
        athlete_items = MeasurementGridService.visible_athlete_items(
            item, viewer, perm_cache
        )

        if MeasurementGridService._order_blocks_editing(item.order):
            # Estado de la orden, no falta de permiso. Antes salia por el
            # PermissionDenied de abajo: quien tenia el grid abierto cuando un
            # admin cerro las medidas recibia un 403 pelado y perdia todo lo
            # tecleado, en vez de un mensaje.
            return SaveResult(
                ok=False,
                errors={"__all__": MeasurementGridService.LOCKED_MESSAGE},
                changed_athlete_items=[],
            )

        editable_ids = MeasurementGridService.editable_athlete_item_ids(
            item, viewer, athlete_items, perm_cache
        )
        if not editable_ids:
            raise PermissionDenied("No puedes editar estas medidas.")

        columns = MeasurementGridService.columns_for(item.product)

        # ── Paso 1: validar TODO antes de tocar la base de datos ───────────
        #
        # Lo obligatorio se exige POR FILA TOCADA, no por celda posteada. El
        # grid vive en un solo <form>: el navegador postea las celdas vacias de
        # todas las filas editables, asi que exigir por celda hacia imposible
        # la captura progresiva -- llenar 5 alumnos de un roster de 30 y
        # guardar devolvia 50 celdas en rojo y cero escrituras, que es
        # justamente lo que un grid del roster tiene que permitir.
        #
        # Una fila esta "tocada" si alguna de sus celdas posteadas difiere de
        # lo guardado. Las intactas se ignoran enteras: ni se validan ni se
        # escriben. Vaciar una celda obligatoria SI cuenta como tocarla, para
        # que nadie deje a medias una fila que ya tenia medidas.
        submitted = {}
        errors = {}
        for athlete_item in athlete_items:
            if athlete_item.id not in editable_ids:
                continue

            existing = {m.field_id: m for m in athlete_item.measurements.all()}

            posted = []
            row_is_touched = False
            for column in columns:
                input_name = f"m-{athlete_item.id}-{column.field_id}"
                if input_name not in post_data:
                    continue
                value = (post_data.get(input_name) or "").strip()
                posted.append((column, input_name, value))

                stored = existing.get(column.field_id)
                if value != (stored.value if stored else ""):
                    row_is_touched = True

            if not row_is_touched:
                continue

            for column, input_name, value in posted:
                if column.required and not value:
                    errors[input_name] = f"'{column.name}' es obligatorio."
                elif len(value) > MeasurementGridService.MAX_VALUE_LENGTH:
                    # OrderItemMeasurement.value es CharField(max_length=50) y
                    # save() llama full_clean(): sin este chequeo, una celda
                    # larga revienta con ValidationError dentro del atomic y
                    # tumba el POST del roster entero con un 500.
                    errors[input_name] = (
                        f"'{column.name}': maximo "
                        f"{MeasurementGridService.MAX_VALUE_LENGTH} caracteres."
                    )
                submitted[(athlete_item.id, column.field_id)] = value

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

                    for column in columns:
                        key = (athlete_item.id, column.field_id)
                        if key not in submitted:
                            continue
                        value = submitted[key]
                        measurement = existing.get(column.field_id)

                        if measurement:
                            if measurement.value != value:
                                measurement.value = value
                                measurement.save()
                                row_changed = True
                        elif value:
                            # Una celda vacía sin fila previa no crea registro:
                            # "" ya significa "sin medida".
                            #
                            # update_or_create y no create: `existing` se leyó
                            # del prefetch ANTES del atomic, asi que dos
                            # capturas simultaneas del mismo roster pueden ver
                            # ambas "sin fila" y crearla a la vez. La segunda
                            # violaria unique_measurement_per_field_per_athlete
                            # con un IntegrityError, que NO es ValidationError
                            # y escaparia del except de abajo como un 500.
                            athlete_item.measurements.update_or_create(
                                field_id=column.field_id,
                                defaults={
                                    "field_name": column.name,
                                    "field_unit": column.unit,
                                    "value": value,
                                },
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
        except IntegrityError as exc:
            # Ultima red: update_or_create resuelve la carrera normal, pero
            # cualquier otra colision de constraint tiene que llegar como
            # error en pantalla y no como 500 con todo lo tecleado perdido.
            logger.warning(
                "Colision al guardar el grid de medidas item=%s viewer=%s: %s",
                item.pk,
                getattr(viewer, "pk", None),
                exc,
            )
            return SaveResult(
                ok=False,
                errors={
                    "__all__": (
                        "Alguien mas guardo estas medidas al mismo tiempo. "
                        "Vuelve a cargar la pagina e intenta de nuevo."
                    )
                },
                changed_athlete_items=[],
            )

        return SaveResult(ok=True, errors={}, changed_athlete_items=changed)
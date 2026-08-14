# orders/tests/test_measurement_grid.py

import pytest
from django.test import Client, TestCase
from django.urls import reverse

from orders.models import OrderItemMeasurement
from orders.services.measurements.MeasurementGridService import (
    MeasurementGridService,
)
from orders.tests.factories import (
    AthleteFactory,
    CoachFactory,
    MeasurementFieldFactory,
    OrderFactory,
    OrderItemAthleteFactory,
    OrderItemFactory,
    ProductMeasurementFieldFactory,
    ProductWithMeasurementsFactory,
    TeamFactory,
    UserTeamMembershipFactory,
)


def make_team_item(field_specs=None):
    """Crea una orden de equipo con un item de producto MEASUREMENTS.

    field_specs: lista de (nombre, order, required). Si es None, el producto
    se queda con los dos campos que crea la factory (Pecho, Cintura).
    Devuelve (coach, team, order, item).
    """
    coach = CoachFactory()
    team = TeamFactory(coach=coach)
    order = OrderFactory(
        order_type="TEAM",
        owner_team=team,
        owner_user=None,
        created_by=coach,
    )
    product = ProductWithMeasurementsFactory(
        usage_type="TEAM_CUSTOM",
        size_strategy="MEASUREMENTS",
    )
    if field_specs is not None:
        product.measurement_fields.all().delete()
        for name, order_value, required in field_specs:
            ProductMeasurementFieldFactory(
                product=product,
                field=MeasurementFieldFactory(name=name, order=order_value),
                required=required,
            )
    item = OrderItemFactory(order=order, product=product)
    return coach, team, order, item


def add_athlete(item, team, first_name="Ana", birth_date=None):
    athlete = AthleteFactory(first_name=first_name)
    if birth_date is not None:
        athlete.birth_date = birth_date
        athlete.save(update_fields=["birth_date"])
    UserTeamMembershipFactory(
        user=athlete,
        team=team,
        role_in_team="ATHLETE",
        status="accepted",
        is_active=True,
    )
    return OrderItemAthleteFactory(order_item=item, athlete=athlete)


def add_minor_with_guardian(item, team, guardian, first_name="Hijo"):
    """Atleta MENOR con tutor asignado.

    OJO: `_is_guardian_of` exige `athlete.is_minor`, y `User.is_minor`
    (accounts/models.py:183) devuelve False cuando `birth_date` es None.
    AthleteFactory NO asigna birth_date, así que sin esta fecha explícita
    todos los tests de guardián fallarían por una causa falsa.
    """
    from datetime import date

    from accounts.models import AthleteProfile

    athlete_item = add_athlete(
        item, team, first_name=first_name, birth_date=date(2015, 5, 1)
    )
    AthleteProfile.objects.update_or_create(
        user=athlete_item.athlete,
        defaults={"guardian": guardian, "emergency_contact": "Tutor"},
    )
    return athlete_item


def reload_item(item):
    """Recarga el item y su orden.

    `item.refresh_from_db()` no basta: `item.order` puede quedar como una
    instancia cacheada con los flags de medidas viejos.
    """
    from orders.models import OrderItem

    return OrderItem.objects.select_related("order", "product").get(pk=item.pk)


@pytest.mark.django_db
class MeasurementGridStructureTests(TestCase):

    def test_columns_use_deterministic_order(self):
        """Las columnas salen por field__order aunque se creen desordenadas."""
        coach, team, order, item = make_team_item(
            field_specs=[("Cadera", 30, True), ("Pecho", 10, True), ("Cintura", 20, True)]
        )
        add_athlete(item, team)

        grid = MeasurementGridService.build(item, coach)

        self.assertEqual(
            [c.name for c in grid.columns],
            ["Pecho", "Cintura", "Cadera"],
        )

    def test_missing_measurement_becomes_placeholder_cell(self):
        """Un atleta sin una medida NO desalinea la fila: la celda existe con '—'."""
        coach, team, order, item = make_team_item(
            field_specs=[("Pecho", 10, True), ("Cintura", 20, True)]
        )
        athlete_item = add_athlete(item, team)
        pecho = item.product.measurement_fields.get(field__name="Pecho").field
        OrderItemMeasurement.objects.create(
            athlete_item=athlete_item,
            field=pecho,
            field_name=pecho.name,
            field_unit=pecho.unit,
            value="90",
        )

        grid = MeasurementGridService.build(item, coach)
        row = grid.rows[0]

        self.assertEqual(len(row.cells), len(grid.columns))
        self.assertEqual(row.cells[0].display_value, "90 cm")
        self.assertEqual(row.cells[1].value, "")
        self.assertEqual(row.cells[1].display_value, "—")

    def test_cells_align_with_columns_by_index(self):
        """cells[i] corresponde siempre a columns[i]."""
        coach, team, order, item = make_team_item(
            field_specs=[("Pecho", 10, True), ("Cintura", 20, True)]
        )
        add_athlete(item, team)

        grid = MeasurementGridService.build(item, coach)
        row = grid.rows[0]

        for index, column in enumerate(grid.columns):
            self.assertEqual(row.cells[index].field_id, column.field_id)

    def test_row_is_complete_when_all_required_filled(self):
        coach, team, order, item = make_team_item(
            field_specs=[("Pecho", 10, True), ("Notas", 20, False)]
        )
        athlete_item = add_athlete(item, team)
        pecho = item.product.measurement_fields.get(field__name="Pecho").field
        OrderItemMeasurement.objects.create(
            athlete_item=athlete_item,
            field=pecho,
            field_name=pecho.name,
            field_unit=pecho.unit,
            value="90",
        )

        grid = MeasurementGridService.build(item, coach)

        self.assertTrue(grid.rows[0].is_complete)
        self.assertEqual(grid.complete_count, 1)
        self.assertEqual(grid.total_count, 1)

    def test_row_is_incomplete_when_required_missing(self):
        coach, team, order, item = make_team_item(
            field_specs=[("Pecho", 10, True), ("Cintura", 20, True)]
        )
        add_athlete(item, team)

        grid = MeasurementGridService.build(item, coach)

        self.assertFalse(grid.rows[0].is_complete)
        self.assertEqual(grid.complete_count, 0)

    def test_product_without_fields_is_never_complete(self):
        """Regla 4.3: producto MEASUREMENTS sin campos configurados no es 'completo'."""
        coach, team, order, item = make_team_item(field_specs=[])
        add_athlete(item, team)

        grid = MeasurementGridService.build(item, coach)

        self.assertEqual(grid.columns, [])
        self.assertFalse(grid.rows[0].is_complete)

    def test_is_complete_matches_model_method(self):
        """La completitud calculada en memoria coincide con has_complete_measurements()."""
        coach, team, order, item = make_team_item(
            field_specs=[("Pecho", 10, True), ("Cintura", 20, True)]
        )
        athlete_item = add_athlete(item, team)
        pecho = item.product.measurement_fields.get(field__name="Pecho").field
        OrderItemMeasurement.objects.create(
            athlete_item=athlete_item,
            field=pecho,
            field_name=pecho.name,
            field_unit=pecho.unit,
            value="90",
        )

        grid = MeasurementGridService.build(item, coach)

        self.assertEqual(
            grid.rows[0].is_complete,
            athlete_item.has_complete_measurements(),
        )

    def test_input_name_format(self):
        coach, team, order, item = make_team_item(
            field_specs=[("Pecho", 10, True)]
        )
        athlete_item = add_athlete(item, team)

        grid = MeasurementGridService.build(item, coach)
        cell = grid.rows[0].cells[0]

        self.assertEqual(
            cell.input_name, f"m-{athlete_item.id}-{cell.field_id}"
        )

    def test_values_override_replaces_stored_value(self):
        """Al re-renderizar tras un error, gana lo tecleado, no lo guardado."""
        coach, team, order, item = make_team_item(
            field_specs=[("Pecho", 10, True)]
        )
        athlete_item = add_athlete(item, team)
        pecho = item.product.measurement_fields.get(field__name="Pecho").field
        OrderItemMeasurement.objects.create(
            athlete_item=athlete_item,
            field=pecho,
            field_name=pecho.name,
            field_unit=pecho.unit,
            value="90",
        )
        name = f"m-{athlete_item.id}-{pecho.id}"

        grid = MeasurementGridService.build(
            item, coach, values={name: "95"}, errors={name: "Ups"}
        )

        self.assertEqual(grid.rows[0].cells[0].value, "95")
        self.assertEqual(grid.rows[0].cells[0].error, "Ups")


from django.core.exceptions import PermissionDenied

from orders.tests.factories import RoleFactory, UserFactory


@pytest.mark.django_db
class MeasurementGridPermissionTests(TestCase):

    def test_coach_creator_sees_all_rows_and_can_edit(self):
        coach, team, order, item = make_team_item(
            field_specs=[("Pecho", 10, True)]
        )
        add_athlete(item, team, first_name="Ana")
        add_athlete(item, team, first_name="Beto")

        grid = MeasurementGridService.build(item, coach)

        self.assertEqual(len(grid.rows), 2)
        self.assertTrue(grid.can_edit)
        self.assertTrue(all(c.editable for r in grid.rows for c in r.cells))

    def test_guardian_sees_only_their_own_athlete(self):
        coach, team, order, item = make_team_item(
            field_specs=[("Pecho", 10, True)]
        )
        guardian = UserFactory()
        mine = add_minor_with_guardian(item, team, guardian, first_name="Hijo")
        add_athlete(item, team, first_name="Ajeno")

        grid = MeasurementGridService.build(item, guardian)

        self.assertEqual(len(grid.rows), 1)
        self.assertEqual(grid.rows[0].athlete_item_id, mine.id)

    def test_stranger_is_denied(self):
        coach, team, order, item = make_team_item(
            field_specs=[("Pecho", 10, True)]
        )
        add_athlete(item, team)
        stranger = UserFactory()

        with self.assertRaises(PermissionDenied):
            MeasurementGridService.build(item, stranger)

    def test_admin_can_edit(self):
        coach, team, order, item = make_team_item(
            field_specs=[("Pecho", 10, True)]
        )
        add_athlete(item, team)
        admin = UserFactory()
        admin.roles.add(RoleFactory(name="ADMIN"))

        grid = MeasurementGridService.build(item, admin)

        self.assertTrue(grid.can_edit)

    def test_cannot_edit_when_measurements_locked(self):
        coach, team, order, item = make_team_item(
            field_specs=[("Pecho", 10, True)]
        )
        add_athlete(item, team)
        order.measurements_locked = True
        order.save()

        grid = MeasurementGridService.build(reload_item(item), coach)

        self.assertFalse(grid.can_edit)
        self.assertFalse(any(c.editable for r in grid.rows for c in r.cells))

    def test_cannot_edit_when_measurements_closed(self):
        coach, team, order, item = make_team_item(
            field_specs=[("Pecho", 10, True)]
        )
        add_athlete(item, team)
        order.measurements_open = False
        order.save()

        grid = MeasurementGridService.build(reload_item(item), coach)

        self.assertFalse(grid.can_edit)


@pytest.mark.django_db
class PiiAccessTypeTests(TestCase):

    def test_edit_measurements_access_type_exists(self):
        from accounts.models import PiiAccessLog

        codes = [code for code, _label in PiiAccessLog.ACCESS_TYPES]
        self.assertIn("EDIT_MEASUREMENTS", codes)


@pytest.mark.django_db
class MeasurementGridSaveTests(TestCase):

    def setUp(self):
        self.coach, self.team, self.order, self.item = make_team_item(
            field_specs=[("Pecho", 10, True), ("Notas", 20, False)]
        )
        self.athlete_item = add_athlete(self.item, self.team, first_name="Ana")
        self.pecho = self.item.product.measurement_fields.get(
            field__name="Pecho"
        ).field
        self.notas = self.item.product.measurement_fields.get(
            field__name="Notas"
        ).field

    def _name(self, athlete_item, field):
        return f"m-{athlete_item.id}-{field.id}"

    def test_saves_submitted_values(self):
        result = MeasurementGridService.save(
            self.item,
            self.coach,
            {self._name(self.athlete_item, self.pecho): "92"},
        )

        self.assertTrue(result.ok)
        measurement = OrderItemMeasurement.objects.get(
            athlete_item=self.athlete_item, field=self.pecho
        )
        self.assertEqual(measurement.value, "92")

    def test_missing_required_field_writes_nothing(self):
        """El error NO debe dejar escrituras parciales."""
        result = MeasurementGridService.save(
            self.item,
            self.coach,
            {
                self._name(self.athlete_item, self.pecho): "",
                self._name(self.athlete_item, self.notas): "algo",
            },
        )

        self.assertFalse(result.ok)
        self.assertIn(self._name(self.athlete_item, self.pecho), result.errors)
        self.assertEqual(
            OrderItemMeasurement.objects.filter(
                athlete_item=self.athlete_item
            ).count(),
            0,
        )

    def test_guardian_cannot_write_other_athletes_cells(self):
        """Test de seguridad central: se asevera contra la BD, no contra el status."""
        guardian = UserFactory()
        mine = add_minor_with_guardian(
            self.item, self.team, guardian, first_name="Hijo"
        )
        other = add_athlete(self.item, self.team, first_name="Ajeno")

        MeasurementGridService.save(
            self.item,
            guardian,
            {
                self._name(mine, self.pecho): "90",
                self._name(other, self.pecho): "199",
            },
        )

        self.assertEqual(
            OrderItemMeasurement.objects.filter(athlete_item=other).count(), 0
        )
        self.assertTrue(
            OrderItemMeasurement.objects.filter(
                athlete_item=mine, value="90"
            ).exists()
        )

    def test_operario_cannot_write(self):
        operario = UserFactory()
        operario.roles.add(RoleFactory(name="OPERARIO"))

        with self.assertRaises(PermissionDenied):
            MeasurementGridService.save(
                self.item,
                operario,
                {self._name(self.athlete_item, self.pecho): "90"},
            )

    def test_locked_measurements_reject_save(self):
        """Rechaza la escritura, pero como estado -- no como falta de permiso.

        Ver LockedOrderTests: el 403 pelado le hacia perder al usuario todo lo
        que habia tecleado.
        """
        self.order.measurements_locked = True
        self.order.save()

        result = MeasurementGridService.save(
            reload_item(self.item),
            self.coach,
            {self._name(self.athlete_item, self.pecho): "90"},
        )

        self.assertFalse(result.ok)
        self.assertEqual(
            result.errors["__all__"], MeasurementGridService.LOCKED_MESSAGE
        )
        self.assertEqual(
            OrderItemMeasurement.objects.filter(
                athlete_item=self.athlete_item
            ).count(),
            0,
        )

    def test_is_modified_only_when_original_existed(self):
        OrderItemMeasurement.objects.create(
            athlete_item=self.athlete_item,
            field=self.pecho,
            field_name=self.pecho.name,
            field_unit=self.pecho.unit,
            value_original="90",
            value="90",
        )

        MeasurementGridService.save(
            self.item,
            self.coach,
            {self._name(self.athlete_item, self.pecho): "95"},
        )

        measurement = OrderItemMeasurement.objects.get(
            athlete_item=self.athlete_item, field=self.pecho
        )
        self.assertEqual(measurement.value, "95")
        self.assertTrue(measurement.is_modified)

    def test_new_measurement_is_not_marked_modified(self):
        MeasurementGridService.save(
            self.item,
            self.coach,
            {self._name(self.athlete_item, self.pecho): "95"},
        )

        measurement = OrderItemMeasurement.objects.get(
            athlete_item=self.athlete_item, field=self.pecho
        )
        self.assertFalse(measurement.is_modified)

    def test_logs_pii_only_for_changed_athletes(self):
        from accounts.models import PiiAccessLog

        other = add_athlete(self.item, self.team, first_name="Beto")
        OrderItemMeasurement.objects.create(
            athlete_item=other,
            field=self.pecho,
            field_name=self.pecho.name,
            field_unit=self.pecho.unit,
            value="80",
        )

        result = MeasurementGridService.save(
            self.item,
            self.coach,
            {
                self._name(self.athlete_item, self.pecho): "92",
                self._name(other, self.pecho): "80",
            },
        )

        self.assertTrue(result.ok)
        changed_ids = [a.id for a in result.changed_athlete_items]
        self.assertEqual(changed_ids, [self.athlete_item.id])


@pytest.mark.django_db
class MeasurementGridViewTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.coach, self.team, self.order, self.item = make_team_item(
            field_specs=[("Pecho", 10, True)]
        )
        self.athlete_item = add_athlete(self.item, self.team, first_name="Ana")
        self.pecho = self.item.product.measurement_fields.get(
            field__name="Pecho"
        ).field
        self.url = reverse(
            "orders:item_measurements_grid", kwargs={"item_id": self.item.id}
        )
        self.input_name = f"m-{self.athlete_item.id}-{self.pecho.id}"

    def test_get_renders_grid(self):
        self.client.force_login(self.coach)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.input_name)

    def test_get_logs_pii_per_athlete(self):
        from accounts.models import PiiAccessLog

        add_athlete(self.item, self.team, first_name="Beto")
        self.client.force_login(self.coach)
        self.client.get(self.url)

        self.assertEqual(
            PiiAccessLog.objects.filter(access_type="VIEW_MEASUREMENTS").count(),
            2,
        )

    def test_post_saves_and_redirects(self):
        self.client.force_login(self.coach)
        response = self.client.post(self.url, {self.input_name: "92"})

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            OrderItemMeasurement.objects.filter(
                athlete_item=self.athlete_item, value="92"
            ).exists()
        )

    def test_post_logs_edit_pii(self):
        from accounts.models import PiiAccessLog

        self.client.force_login(self.coach)
        self.client.post(self.url, {self.input_name: "92"})

        self.assertEqual(
            PiiAccessLog.objects.filter(
                access_type="EDIT_MEASUREMENTS",
                target_user=self.athlete_item.athlete,
            ).count(),
            1,
        )

    def test_post_with_error_keeps_typed_values(self):
        """El bug que este trabajo arregla: un error no debe tirar lo tecleado.

        La celda de Ana lleva un valor invalido (no vacio): una celda vacia en
        una fila que nadie toco ya no es error, es una fila sin capturar.
        """
        add_athlete(self.item, self.team, first_name="Beto")
        beto_item = self.item.athletes.get(athlete__first_name="Beto")
        beto_name = f"m-{beto_item.id}-{self.pecho.id}"

        self.client.force_login(self.coach)
        response = self.client.post(
            self.url, {self.input_name: "x" * 62, beto_name: "88"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="88"')
        self.assertEqual(OrderItemMeasurement.objects.count(), 0)

    def test_operario_post_is_forbidden(self):
        operario = UserFactory()
        operario.roles.add(RoleFactory(name="OPERARIO"))
        self.client.force_login(operario)

        response = self.client.post(self.url, {self.input_name: "92"})

        self.assertEqual(response.status_code, 403)

    def test_stranger_get_is_forbidden(self):
        self.client.force_login(UserFactory())
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)

@pytest.mark.django_db
class SingleWritePathTests(TestCase):

    def test_old_write_endpoint_is_gone(self):
        """Un segundo camino de escritura sin auditar reabriria el hueco de PII."""
        from django.urls import NoReverseMatch

        with self.assertRaises(NoReverseMatch):
            reverse(
                "orders:item_measurements_order_add",
                kwargs={"athlete_item_id": 1},
            )


@pytest.mark.django_db
class ItemDetailGridEmbedTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.coach, self.team, self.order, self.item = make_team_item(
            field_specs=[("Pecho", 10, True)]
        )
        self.athlete_item = add_athlete(self.item, self.team, first_name="Ana")

    def test_item_detail_shows_grid_with_athlete_name(self):
        self.client.force_login(self.coach)
        url = reverse("orders:order_item_detail", kwargs={"item_id": self.item.id})

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.context["grid"])
        self.assertContains(response, "Ana")
        self.assertContains(response, "Pecho")


@pytest.mark.django_db
class AdminAndOperarioGridTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.coach, self.team, self.order, self.item = make_team_item(
            field_specs=[("Pecho", 10, True)]
        )
        self.athlete_item = add_athlete(self.item, self.team, first_name="Ana")
        pecho = self.item.product.measurement_fields.get(field__name="Pecho").field
        OrderItemMeasurement.objects.create(
            athlete_item=self.athlete_item,
            field=pecho,
            field_name=pecho.name,
            field_unit=pecho.unit,
            value="92",
        )
        self.admin = UserFactory(profile_completed=True)
        self.admin.roles.add(RoleFactory(name="ADMIN"))

    def test_admin_order_detail_shows_measurement_values(self):
        """Hoy el admin solo ve badges: ni un solo valor."""
        self.client.force_login(self.admin)
        url = reverse(
            "orders:admin_order_detail", kwargs={"order_id": self.order.id}
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "92")
        self.assertIn(self.item.id, response.context["grids"])


@pytest.mark.django_db
class MeasurementGridQueryCountTests(TestCase):

    def _guardian_item_with(self, athlete_count):
        """Item visto por un GUARDIAN.

        Es el viewer que dispara el N+1 de verdad: `_sees_every_row` devuelve
        False, asi que `_is_guardian_of` se evalua sobre TODAS las filas y toca
        `athlete.athleteprofile` una por una. Con un coach el conteo ya sale
        plano porque `_sees_every_row` corta antes, y el test no probaria nada.
        """
        coach, team, order, item = make_team_item(
            field_specs=[("Pecho", 10, True), ("Cintura", 20, True)]
        )
        guardian = UserFactory()
        add_minor_with_guardian(item, team, guardian, first_name="Hijo")
        for index in range(athlete_count - 1):
            add_athlete(item, team, first_name=f"Atleta{index}")
        return guardian, item

    def _coach_item_with(self, athlete_count):
        coach, team, order, item = make_team_item(
            field_specs=[("Pecho", 10, True), ("Cintura", 20, True)]
        )
        for index in range(athlete_count):
            add_athlete(item, team, first_name=f"Atleta{index}")
        return coach, item

    def test_query_count_is_flat_for_guardian(self):
        """build() hace las mismas consultas con 2 atletas que con 10.

        Se comparan dos tamanos en vez de fijar un numero magico: un numero
        exacto se rompe con cualquier refactor legitimo y no dice nada sobre
        si el costo escala, que es lo unico que importa aqui.
        """
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        guardian_small, small_item = self._guardian_item_with(2)
        guardian_big, big_item = self._guardian_item_with(10)

        with CaptureQueriesContext(connection) as small:
            MeasurementGridService.build(small_item, guardian_small)
        with CaptureQueriesContext(connection) as big:
            MeasurementGridService.build(big_item, guardian_big)

        self.assertEqual(len(small.captured_queries), len(big.captured_queries))

    def test_grid_view_query_count_is_flat(self):
        """La vista completa, con el logging de PII incluido, tampoco escala.

        El log de PII SI crece con el numero de atletas (un INSERT por sujeto,
        exigido por la auditoria). Este test mide solo las consultas de LECTURA.
        """
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        coach_small, small_item = self._coach_item_with(2)
        coach_big, big_item = self._coach_item_with(10)

        client = Client()

        client.force_login(coach_small)
        with CaptureQueriesContext(connection) as small:
            client.get(
                reverse(
                    "orders:item_measurements_grid",
                    kwargs={"item_id": small_item.id},
                )
            )

        client.force_login(coach_big)
        with CaptureQueriesContext(connection) as big:
            client.get(
                reverse(
                    "orders:item_measurements_grid",
                    kwargs={"item_id": big_item.id},
                )
            )

        def reads(context):
            return [
                q
                for q in context.captured_queries
                if not q["sql"].lstrip().upper().startswith("INSERT")
            ]

        self.assertEqual(len(reads(small)), len(reads(big)))


@pytest.mark.django_db
class FinalReviewFindingsTests(TestCase):
    """Hallazgos de la revision final de rama (2026-08-11)."""

    def setUp(self):
        self.client = Client()
        self.coach, self.team, self.order, self.item = make_team_item(
            field_specs=[("Pecho", 10, True), ("Notas", 20, False)]
        )
        self.ana = add_athlete(self.item, self.team, first_name="Ana")
        self.beto = add_athlete(self.item, self.team, first_name="Beto")
        self.pecho = self.item.product.measurement_fields.get(
            field__name="Pecho"
        ).field
        self.notas = self.item.product.measurement_fields.get(
            field__name="Notas"
        ).field

    def _log_count(self):
        from accounts.models import PiiAccessLog

        return PiiAccessLog.objects.filter(
            access_type="VIEW_MEASUREMENTS"
        ).count()

    def test_c1_admin_order_detail_logs_pii_per_athlete(self):
        """C1: el admin ve medidas de menores; debe quedar rastro por sujeto."""
        admin = UserFactory(profile_completed=True)
        admin.roles.add(RoleFactory(name="ADMIN"))
        self.client.force_login(admin)

        self.client.get(
            reverse("orders:admin_order_detail", kwargs={"order_id": self.order.id})
        )

        self.assertEqual(self._log_count(), 2)

    def test_i2_item_detail_logs_pii_per_athlete(self):
        """I2: el coach ve el roster completo en el detalle del item."""
        self.client.force_login(self.coach)

        self.client.get(
            reverse("orders:order_item_detail", kwargs={"item_id": self.item.id})
        )

        self.assertEqual(self._log_count(), 2)

    def test_i3_guardian_post_lands_on_a_reachable_page(self):
        """I3: la tutora guardaba bien y caia en un 404."""
        guardian = UserFactory()
        mine = add_minor_with_guardian(
            self.item, self.team, guardian, first_name="Hija"
        )
        self.client.force_login(guardian)

        response = self.client.post(
            reverse("orders:item_measurements_grid", kwargs={"item_id": self.item.id}),
            {f"m-{mine.id}-{self.pecho.id}": "90"},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            OrderItemMeasurement.objects.filter(athlete_item=mine, value="90").exists()
        )

    def test_i4_too_long_value_is_a_cell_error_not_a_500(self):
        """I4: value es CharField(max_length=50); 62 caracteres tumbaban el POST."""
        self.client.force_login(self.coach)

        response = self.client.post(
            reverse("orders:item_measurements_grid", kwargs={"item_id": self.item.id}),
            {
                f"m-{self.ana.id}-{self.pecho.id}": "90",
                f"m-{self.ana.id}-{self.notas.id}": "x" * 62,
                f"m-{self.beto.id}-{self.pecho.id}": "88",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(OrderItemMeasurement.objects.count(), 0)
        self.assertContains(response, "88")

    def test_i5_athlete_page_shows_only_that_athlete(self):
        """I5: la pagina 'Medidas de Ana' mostraba a todo el equipo."""
        self.client.force_login(self.coach)

        response = self.client.get(
            reverse(
                "orders:order_item_measurements",
                kwargs={"athlete_item_id": self.ana.id},
            )
        )

        self.assertEqual(len(response.context["grid"].rows), 1)
        self.assertEqual(response.context["grid"].rows[0].athlete_item_id, self.ana.id)
        self.assertEqual(self._log_count(), 1)


@pytest.mark.django_db
class SaveValidationErrorSurfacingTests(TestCase):
    """El error global del except ValidationError debe llegar al usuario.

    Sin esto el usuario lee "Revisa los campos marcados" sin que ninguna celda
    este marcada, porque el template solo pinta errores por celda.
    """

    def setUp(self):
        self.client = Client()
        self.coach, self.team, self.order, self.item = make_team_item(
            field_specs=[("Pecho", 10, True)]
        )
        self.athlete_item = add_athlete(self.item, self.team, first_name="Ana")
        self.pecho = self.item.product.measurement_fields.get(
            field__name="Pecho"
        ).field
        self.input_name = f"m-{self.athlete_item.id}-{self.pecho.id}"

    def test_model_validation_error_becomes_a_visible_message(self):
        from unittest.mock import patch

        from django.core.exceptions import ValidationError as DjangoValidationError

        self.client.force_login(self.coach)

        with patch(
            "orders.models.OrderItemMeasurement.save",
            side_effect=DjangoValidationError("Las medidas no pueden editarse"),
        ):
            response = self.client.post(
                reverse(
                    "orders:item_measurements_grid",
                    kwargs={"item_id": self.item.id},
                ),
                {self.input_name: "92"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(OrderItemMeasurement.objects.count(), 0)
        self.assertContains(response, "Las medidas no pueden editarse")


@pytest.mark.django_db
class PermCacheTests(TestCase):
    """El panel admin arma un grid por item de la misma orden.

    Sin cache compartido repetia las consultas de permisos (roles del viewer y
    visibilidad de la orden) una vez por item.
    """

    def setUp(self):
        self.coach, self.team, self.order, self.item = make_team_item(
            field_specs=[("Pecho", 10, True)]
        )
        self.item2 = OrderItemFactory(order=self.order, product=self.item.product)
        add_athlete(self.item, self.team, first_name="Ana")
        add_athlete(self.item2, self.team, first_name="Beto")
        # ADMIN que NO creo la orden: asi `is_privileged` no corta antes de
        # consultar los roles y el cache tiene algo real que ahorrar.
        self.admin = UserFactory(profile_completed=True)
        self.admin.roles.add(RoleFactory(name="ADMIN"))

    def _second_build_queries(self, shared_cache):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        first_cache = {} if shared_cache else None
        MeasurementGridService.build(
            reload_item(self.item), self.admin, perm_cache=first_cache
        )
        with CaptureQueriesContext(connection) as ctx:
            MeasurementGridService.build(
                reload_item(self.item2),
                self.admin,
                perm_cache=first_cache if shared_cache else None,
            )
        return len(ctx.captured_queries)

    def test_shared_cache_saves_permission_queries(self):
        cached = self._second_build_queries(shared_cache=True)
        uncached = self._second_build_queries(shared_cache=False)

        self.assertLess(cached, uncached)

    def test_shared_cache_does_not_change_the_result(self):
        shared = {}
        with_cache = MeasurementGridService.build(
            reload_item(self.item2), self.admin, perm_cache=shared
        )
        without_cache = MeasurementGridService.build(
            reload_item(self.item2), self.admin
        )

        self.assertEqual(with_cache.can_edit, without_cache.can_edit)
        self.assertEqual(
            [row.athlete_item_id for row in with_cache.rows],
            [row.athlete_item_id for row in without_cache.rows],
        )


@pytest.mark.django_db
class PiiLogVolumeTests(TestCase):
    """Una bitacora que se duplica en cada F5 deja de servir para investigar."""

    def setUp(self):
        self.client = Client()
        self.coach, self.team, self.order, self.item = make_team_item(
            field_specs=[("Pecho", 10, True)]
        )
        self.ana = add_athlete(self.item, self.team, first_name="Ana")
        self.beto = add_athlete(self.item, self.team, first_name="Beto")
        self.pecho = self.item.product.measurement_fields.get(
            field__name="Pecho"
        ).field
        self.url = reverse(
            "orders:item_measurements_grid", kwargs={"item_id": self.item.id}
        )

    def _view_logs(self):
        from accounts.models import PiiAccessLog

        return PiiAccessLog.objects.filter(access_type="VIEW_MEASUREMENTS")

    def test_refresh_within_window_does_not_duplicate_logs(self):
        self.client.force_login(self.coach)

        self.client.get(self.url)
        self.client.get(self.url)
        self.client.get(self.url)

        self.assertEqual(self._view_logs().count(), 2)

    def test_first_view_still_logs_every_subject(self):
        self.client.force_login(self.coach)

        self.client.get(self.url)

        self.assertEqual(
            set(self._view_logs().values_list("target_user_id", flat=True)),
            {self.ana.athlete_id, self.beto.athlete_id},
        )

    def test_a_different_viewer_gets_its_own_log(self):
        """La deduplicacion es por actor: otro usuario deja su propio rastro."""
        admin = UserFactory(profile_completed=True)
        admin.roles.add(RoleFactory(name="ADMIN"))

        self.client.force_login(self.coach)
        self.client.get(self.url)
        self.client.force_login(admin)
        self.client.get(self.url)

        self.assertEqual(self._view_logs().count(), 4)

    def test_expired_window_logs_again(self):
        from accounts.models import PiiAccessLog

        self.client.force_login(self.coach)
        self.client.get(self.url)
        # Envejece los registros mas alla de la ventana de deduplicacion.
        from datetime import timedelta

        from django.utils import timezone

        PiiAccessLog.objects.update(
            timestamp=timezone.now() - timedelta(hours=2)
        )

        self.client.get(self.url)

        self.assertEqual(self._view_logs().count(), 4)

    def test_failed_post_without_previous_get_audits_the_roster(self):
        """El POST fallido re-renderiza el grid completo: se ve, se audita.

        Sin GET previo a proposito: es el caso donde antes se mostraba el
        roster entero sin dejar ningun rastro.
        """
        self.client.force_login(self.coach)

        # Valor invalido, no celda vacia: una fila que nadie toco ya no falla.
        response = self.client.post(
            self.url, {f"m-{self.ana.id}-{self.pecho.id}": "x" * 62}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(OrderItemMeasurement.objects.count(), 0)
        self.assertEqual(self._view_logs().count(), 2)

    def test_get_then_failed_post_coalesces_into_one_record(self):
        """Documenta la interaccion entre las dos reglas.

        En el flujo real (abrir la pagina, guardar mal) el GET ya auditó a
        todos, asi que el re-render NO agrega un segundo registro. El acceso
        queda asentado una vez, que es lo que la ventana busca; no es que el
        re-render se quede sin auditar.
        """
        self.client.force_login(self.coach)

        self.client.get(self.url)
        self.client.post(self.url, {f"m-{self.ana.id}-{self.pecho.id}": "x" * 62})

        self.assertEqual(self._view_logs().count(), 2)

    def test_a_different_surface_leaves_its_own_record(self):
        """`notes` entra en la clave: el panel admin y el grid no colapsan."""
        admin = UserFactory(profile_completed=True)
        admin.roles.add(RoleFactory(name="ADMIN"))
        self.client.force_login(admin)

        self.client.get(self.url)
        self.client.get(
            reverse("orders:admin_order_detail", kwargs={"order_id": self.order.id})
        )

        self.assertEqual(self._view_logs().count(), 4)
        self.assertEqual(
            self._view_logs().values("notes").distinct().count(), 2
        )


@pytest.mark.django_db
class LockedOrderTests(TestCase):
    """Orden bloqueada != sin permiso. Lo primero es un mensaje, no un 403."""

    def setUp(self):
        self.client = Client()
        self.coach, self.team, self.order, self.item = make_team_item(
            field_specs=[("Pecho", 10, True)]
        )
        self.athlete_item = add_athlete(self.item, self.team, first_name="Ana")
        self.pecho = self.item.product.measurement_fields.get(
            field__name="Pecho"
        ).field
        self.url = reverse(
            "orders:item_measurements_grid", kwargs={"item_id": self.item.id}
        )
        self.input_name = f"m-{self.athlete_item.id}-{self.pecho.id}"

    def _lock(self):
        self.order.measurements_locked = True
        self.order.save(update_fields=["measurements_locked"])

    def test_saving_a_locked_order_is_a_message_not_a_403(self):
        self._lock()
        self.client.force_login(self.coach)

        response = self.client.post(self.url, {self.input_name: "92"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "cerradas o bloqueadas")
        self.assertEqual(OrderItemMeasurement.objects.count(), 0)

    def test_service_reports_locked_instead_of_raising(self):
        self._lock()

        result = MeasurementGridService.save(
            reload_item(self.item), self.coach, {self.input_name: "92"}
        )

        self.assertFalse(result.ok)
        self.assertEqual(
            result.errors["__all__"], MeasurementGridService.LOCKED_MESSAGE
        )

    def test_a_stranger_still_gets_403_on_a_locked_order(self):
        """El bloqueo no debe convertirse en un canal de informacion."""
        self._lock()
        stranger = CoachFactory()

        with self.assertRaises(PermissionDenied):
            MeasurementGridService.save(
                reload_item(self.item), stranger, {self.input_name: "92"}
            )

    def test_grid_marks_the_order_as_locked(self):
        self._lock()

        grid = MeasurementGridService.build(reload_item(self.item), self.coach)

        self.assertFalse(grid.can_edit)
        self.assertTrue(grid.is_locked)

    def test_open_order_without_write_rights_is_not_locked(self):
        """El coach del equipo ve la orden pero no la creo: no puede escribir.

        La pantalla le decia "cerradas o bloqueadas", que es falso.
        """
        other_coach = CoachFactory()
        self.team.coach = other_coach
        self.team.save(update_fields=["coach"])

        grid = MeasurementGridService.build(reload_item(self.item), other_coach)

        self.assertFalse(grid.can_edit)
        self.assertFalse(grid.is_locked)


@pytest.mark.django_db
class OrphanColumnTests(TestCase):
    """Quitar un campo del producto no debe borrar de la vista lo capturado."""

    def setUp(self):
        self.coach, self.team, self.order, self.item = make_team_item(
            field_specs=[("Pecho", 10, True), ("Cintura", 20, False)]
        )
        self.athlete_item = add_athlete(self.item, self.team, first_name="Ana")
        self.pecho = self.item.product.measurement_fields.get(
            field__name="Pecho"
        ).field
        self.cintura = self.item.product.measurement_fields.get(
            field__name="Cintura"
        ).field
        for field, value in ((self.pecho, "90"), (self.cintura, "70")):
            OrderItemMeasurement.objects.create(
                athlete_item=self.athlete_item,
                field=field,
                field_name=field.name,
                field_unit=field.unit,
                value=value,
            )

    def _detach_cintura(self):
        self.item.product.measurement_fields.filter(field=self.cintura).delete()

    def test_detached_field_still_shows_its_value(self):
        self._detach_cintura()

        grid = MeasurementGridService.build(reload_item(self.item), self.coach)

        orphans = [c for c in grid.columns if c.is_orphan]
        self.assertEqual([c.name for c in orphans], ["Cintura"])
        cell = grid.rows[0].cells[-1]
        self.assertEqual(cell.value, "70")

    def test_orphan_cells_are_never_editable(self):
        """OrderItemMeasurement.clean() rechaza campos ajenos al producto."""
        self._detach_cintura()

        grid = MeasurementGridService.build(reload_item(self.item), self.coach)

        orphan_cells = [
            cell
            for row in grid.rows
            for cell in row.cells
            if cell.field_name == "Cintura"
        ]
        self.assertTrue(orphan_cells)
        self.assertFalse(any(cell.editable for cell in orphan_cells))

    def test_posting_an_orphan_cell_is_ignored(self):
        self._detach_cintura()

        result = MeasurementGridService.save(
            reload_item(self.item),
            self.coach,
            {
                f"m-{self.athlete_item.id}-{self.pecho.id}": "91",
                f"m-{self.athlete_item.id}-{self.cintura.id}": "999",
            },
        )

        self.assertTrue(result.ok)
        self.assertEqual(
            OrderItemMeasurement.objects.get(
                athlete_item=self.athlete_item, field=self.cintura
            ).value,
            "70",
        )

    def test_an_empty_detached_field_adds_no_column(self):
        """Solo se rescata lo que tiene dato; una huerfana vacia es ruido."""
        OrderItemMeasurement.objects.filter(field=self.cintura).update(value="")
        self._detach_cintura()

        grid = MeasurementGridService.build(reload_item(self.item), self.coach)

        self.assertFalse([c for c in grid.columns if c.is_orphan])

    def test_orphans_do_not_make_a_fieldless_product_complete(self):
        """Un producto sin campos configurados nunca cuenta como completo."""
        self.item.product.measurement_fields.all().delete()

        grid = MeasurementGridService.build(reload_item(self.item), self.coach)

        self.assertTrue([c for c in grid.columns if c.is_orphan])
        self.assertFalse(grid.rows[0].is_complete)


@pytest.mark.django_db
class GridPrefetchReuseTests(TestCase):
    """El grid rehacia la consulta de atletas e invalidaba el prefetch."""

    def setUp(self):
        self.coach, self.team, self.order, self.item = make_team_item(
            field_specs=[("Pecho", 10, True)]
        )
        add_athlete(self.item, self.team, first_name="Ana")
        add_athlete(self.item, self.team, first_name="Beto")

    def test_prefetched_athletes_are_reused(self):
        from django.db import connection
        from django.db.models import Prefetch
        from django.test.utils import CaptureQueriesContext

        from orders.models import OrderItem, OrderItemAthlete

        item = OrderItem.objects.select_related("order", "product").prefetch_related(
            Prefetch(
                "athletes",
                queryset=OrderItemAthlete.objects.select_related(
                    "athlete", "athlete__athleteprofile"
                ).prefetch_related("measurements"),
            )
        ).get(pk=self.item.pk)

        with CaptureQueriesContext(connection) as ctx:
            athlete_items = MeasurementGridService.athlete_items_for(item)

        self.assertEqual(len(athlete_items), 2)
        self.assertEqual(len(ctx.captured_queries), 0)

    def test_order_is_the_same_with_and_without_prefetch(self):
        from django.db.models import Prefetch

        from orders.models import OrderItem, OrderItemAthlete

        without = MeasurementGridService.athlete_items_for(reload_item(self.item))
        prefetched = OrderItem.objects.prefetch_related(
            Prefetch(
                "athletes",
                # Orden deliberadamente invertido: el servicio debe imponer el suyo.
                queryset=OrderItemAthlete.objects.select_related("athlete").order_by(
                    "-athlete__first_name"
                ),
            )
        ).get(pk=self.item.pk)
        with_prefetch = MeasurementGridService.athlete_items_for(prefetched)

        self.assertEqual(
            [a.id for a in without], [a.id for a in with_prefetch]
        )


@pytest.mark.django_db
class NonMeasurementProductTests(TestCase):
    """El grid perdio el guard que order_item_measurements si conserva."""

    def test_grid_redirects_for_a_product_without_measurements(self):
        """Producto de catalogo normal: no usa medidas, el grid no aplica.

        Ojo: no se puede tomar un producto MEASUREMENTS y degradarlo, porque
        `Product.clean()` exige talla o medidas en los personalizados y ademas
        congela `size_strategy` una vez usado en una orden.
        """
        from orders.tests.factories import ProductFactory

        coach = CoachFactory()
        order = OrderFactory(created_by=coach, owner_user=coach)
        product = ProductFactory(usage_type="GLOBAL", size_strategy="NONE")
        item = OrderItemFactory(order=order, product=product)

        client = Client()
        client.force_login(coach)
        response = client.post(
            reverse("orders:item_measurements_grid", kwargs={"item_id": item.id}),
            {"cualquier": "cosa"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(OrderItemMeasurement.objects.count(), 0)


@pytest.mark.django_db
class PartialCaptureTests(TestCase):
    """El grid vive en un solo <form>: el navegador postea TODAS las celdas.

    Exigir los obligatorios por celda posteada hacia imposible capturar de a
    poco: llenar 5 alumnos de 30 y guardar devolvia el roster entero en rojo y
    no escribia nada.
    """

    def setUp(self):
        self.coach, self.team, self.order, self.item = make_team_item(
            field_specs=[("Pecho", 10, True), ("Notas", 20, False)]
        )
        self.ana = add_athlete(self.item, self.team, first_name="Ana")
        self.beto = add_athlete(self.item, self.team, first_name="Beto")
        self.cami = add_athlete(self.item, self.team, first_name="Cami")
        self.pecho = self.item.product.measurement_fields.get(
            field__name="Pecho"
        ).field
        self.notas = self.item.product.measurement_fields.get(
            field__name="Notas"
        ).field

    def _name(self, athlete_item, field):
        return f"m-{athlete_item.id}-{field.id}"

    def _full_post(self, **filled):
        """Postea TODAS las celdas del roster, como hace el navegador."""
        post = {}
        for athlete_item in (self.ana, self.beto, self.cami):
            for field in (self.pecho, self.notas):
                post[self._name(athlete_item, field)] = ""
        post.update(filled)
        return post

    def test_filling_one_row_of_three_saves_it(self):
        result = MeasurementGridService.save(
            reload_item(self.item),
            self.coach,
            self._full_post(**{self._name(self.ana, self.pecho): "90"}),
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.errors, {})
        self.assertEqual(
            [a.id for a in result.changed_athlete_items], [self.ana.id]
        )
        self.assertEqual(OrderItemMeasurement.objects.count(), 1)

    def test_empty_rows_do_not_raise_required_errors(self):
        """Beto y Cami van vacios: son filas sin capturar, no filas invalidas."""
        result = MeasurementGridService.save(
            reload_item(self.item),
            self.coach,
            self._full_post(**{self._name(self.ana, self.pecho): "90"}),
        )

        self.assertNotIn(self._name(self.beto, self.pecho), result.errors)
        self.assertNotIn(self._name(self.cami, self.pecho), result.errors)
        self.assertFalse(
            OrderItemMeasurement.objects.filter(
                athlete_item__in=[self.beto.id, self.cami.id]
            ).exists()
        )

    def test_touched_row_must_complete_its_required_cells(self):
        """Si tocaste la fila, el obligatorio de ESA fila si se exige."""
        result = MeasurementGridService.save(
            reload_item(self.item),
            self.coach,
            self._full_post(**{self._name(self.beto, self.notas): "solo notas"}),
        )

        self.assertFalse(result.ok)
        self.assertIn(self._name(self.beto, self.pecho), result.errors)
        self.assertEqual(OrderItemMeasurement.objects.count(), 0)

    def test_clearing_a_required_cell_that_had_a_value_is_an_error(self):
        """Vaciar cuenta como tocar: no se deja a medias una fila ya capturada."""
        OrderItemMeasurement.objects.create(
            athlete_item=self.ana,
            field=self.pecho,
            field_name=self.pecho.name,
            field_unit=self.pecho.unit,
            value="90",
        )

        result = MeasurementGridService.save(
            reload_item(self.item), self.coach, self._full_post()
        )

        self.assertFalse(result.ok)
        self.assertIn(self._name(self.ana, self.pecho), result.errors)
        self.assertEqual(
            OrderItemMeasurement.objects.get(athlete_item=self.ana).value, "90"
        )

    def test_clearing_an_optional_cell_works(self):
        OrderItemMeasurement.objects.create(
            athlete_item=self.ana,
            field=self.notas,
            field_name=self.notas.name,
            field_unit=self.notas.unit,
            value="algo",
        )

        result = MeasurementGridService.save(
            reload_item(self.item),
            self.coach,
            self._full_post(**{self._name(self.ana, self.pecho): "90"}),
        )

        self.assertTrue(result.ok)
        self.assertEqual(
            OrderItemMeasurement.objects.get(
                athlete_item=self.ana, field=self.notas
            ).value,
            "",
        )

    def test_reposting_the_same_values_changes_nothing(self):
        OrderItemMeasurement.objects.create(
            athlete_item=self.ana,
            field=self.pecho,
            field_name=self.pecho.name,
            field_unit=self.pecho.unit,
            value="90",
        )

        result = MeasurementGridService.save(
            reload_item(self.item),
            self.coach,
            self._full_post(**{self._name(self.ana, self.pecho): "90"}),
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.changed_athlete_items, [])

    def test_progressive_capture_across_two_saves(self):
        """El caso real: hoy llegaron 1 y 2, manana el tercero."""
        item = reload_item(self.item)
        MeasurementGridService.save(
            item,
            self.coach,
            self._full_post(**{self._name(self.ana, self.pecho): "90"}),
        )
        result = MeasurementGridService.save(
            reload_item(self.item),
            self.coach,
            self._full_post(
                **{
                    self._name(self.ana, self.pecho): "90",
                    self._name(self.beto, self.pecho): "88",
                }
            ),
        )

        self.assertTrue(result.ok)
        self.assertEqual([a.id for a in result.changed_athlete_items], [self.beto.id])
        self.assertEqual(OrderItemMeasurement.objects.count(), 2)


@pytest.mark.django_db
class ConcurrentSaveTests(TestCase):
    """Dos capturas simultaneas del mismo roster no deben dar 500."""

    def setUp(self):
        self.coach, self.team, self.order, self.item = make_team_item(
            field_specs=[("Pecho", 10, True)]
        )
        self.athlete_item = add_athlete(self.item, self.team, first_name="Ana")
        self.pecho = self.item.product.measurement_fields.get(
            field__name="Pecho"
        ).field
        self.input_name = f"m-{self.athlete_item.id}-{self.pecho.id}"

    def _stale_athlete_items(self):
        """Filas leidas ANTES de que la otra sesion escriba: prefetch vacio."""
        athlete_items = MeasurementGridService.visible_athlete_items(
            reload_item(self.item), self.coach
        )
        for athlete_item in athlete_items:
            list(athlete_item.measurements.all())
        return athlete_items

    def test_row_created_by_someone_else_is_updated_not_duplicated(self):
        from unittest.mock import patch

        stale = self._stale_athlete_items()

        # La otra sesion crea la fila que `stale` cree inexistente.
        OrderItemMeasurement.objects.create(
            athlete_item=self.athlete_item,
            field=self.pecho,
            field_name=self.pecho.name,
            field_unit=self.pecho.unit,
            value="70",
        )

        with patch.object(
            MeasurementGridService, "visible_athlete_items", return_value=stale
        ):
            result = MeasurementGridService.save(
                reload_item(self.item), self.coach, {self.input_name: "92"}
            )

        self.assertTrue(result.ok)
        rows = OrderItemMeasurement.objects.filter(athlete_item=self.athlete_item)
        self.assertEqual(rows.count(), 1)
        self.assertEqual(rows.get().value, "92")

    def test_integrity_error_becomes_a_visible_message_not_a_500(self):
        from unittest.mock import patch

        from django.db import IntegrityError

        with patch(
            "orders.models.OrderItemMeasurement.save",
            side_effect=IntegrityError("duplicate key"),
        ):
            result = MeasurementGridService.save(
                reload_item(self.item), self.coach, {self.input_name: "92"}
            )

        self.assertFalse(result.ok)
        self.assertIn("__all__", result.errors)
        self.assertEqual(OrderItemMeasurement.objects.count(), 0)

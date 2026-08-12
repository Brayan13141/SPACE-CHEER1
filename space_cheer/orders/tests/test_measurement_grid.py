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
            [c.field.name for c in grid.columns],
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
        self.order.measurements_locked = True
        self.order.save()

        with self.assertRaises(PermissionDenied):
            MeasurementGridService.save(
                reload_item(self.item),
                self.coach,
                {self._name(self.athlete_item, self.pecho): "90"},
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
        """El bug que este trabajo arregla: un error no debe tirar lo tecleado."""
        add_athlete(self.item, self.team, first_name="Beto")
        beto_item = self.item.athletes.get(athlete__first_name="Beto")
        beto_name = f"m-{beto_item.id}-{self.pecho.id}"

        self.client.force_login(self.coach)
        response = self.client.post(
            self.url, {self.input_name: "", beto_name: "88"}
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
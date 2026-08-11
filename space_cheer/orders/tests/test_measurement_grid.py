# orders/tests/test_measurement_grid.py

import pytest
from django.test import TestCase

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
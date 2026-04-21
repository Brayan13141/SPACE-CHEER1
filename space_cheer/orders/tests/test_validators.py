from django.test import TestCase
from django.core.exceptions import ValidationError
from decimal import Decimal

from orders.tests.factories import (
    OrderFactory,
    TeamOrderFactory,
    OrderItemFactory,
    OrderItemAthleteFactory,
    ProductFactory,
    ProductWithMeasurementsFactory,
    AthleteFactory,
    TeamFactory,
    UserTeamMembershipFactory,
    OrderContactInfoFactory,
)
from orders.services.validators import (
    OrderBaseValidator,
    OrderAthleteValidator,
    OrderDesignValidator,
    OrderMeasurementsValidator,
)
from orders.services.contactinfo import OrderContactValidator


class OrderBaseValidatorTests(TestCase):
    """Tests para OrderBaseValidator"""

    def test_validate_owner_personal_valid(self):
        """Orden PERSONAL con owner_user es válida"""
        order = OrderFactory(order_type="PERSONAL")
        # No debería lanzar excepción
        OrderBaseValidator.validate_owner(order)

    def test_validate_owner_personal_without_user(self):
        """Orden PERSONAL sin owner_user es inválida"""
        order = OrderFactory.build(
            order_type="PERSONAL", owner_user=None, owner_team=None
        )

        with self.assertRaises(ValidationError) as cm:
            OrderBaseValidator.validate_owner(order)

        self.assertIn("dueño", str(cm.exception).lower())

    def test_validate_owner_personal_with_team(self):
        """Orden PERSONAL no puede tener owner_team"""
        team = TeamFactory()
        order = OrderFactory.build(order_type="PERSONAL", owner_team=team)

        with self.assertRaises(ValidationError):
            OrderBaseValidator.validate_owner(order)

    def test_validate_owner_team_valid(self):
        """Orden TEAM con owner_team es válida"""
        order = TeamOrderFactory()
        OrderBaseValidator.validate_owner(order)

    def test_validate_owner_team_without_team(self):
        """Orden TEAM sin owner_team es inválida"""
        order = OrderFactory.build(order_type="TEAM", owner_user=None, owner_team=None)

        with self.assertRaises(ValidationError):
            OrderBaseValidator.validate_owner(order)

    def test_validate_contact_missing(self):
        """Falla si no existe contact_info"""
        order = OrderFactory()
        order.save()  # Guardar para que tenga pk

        with self.assertRaises(ValidationError):
            OrderBaseValidator.validate_contact(order)

    def test_validate_contact_incomplete(self):
        """Falla si contact_info está incompleto"""
        order = OrderFactory()
        OrderContactInfoFactory(
            order=order,
            contact_name="",  # Campo vacío
            contact_phone="5512345678",
            contact_email="test@test.com",
            shipping_address_line="Calle 123",
            shipping_city="CDMX",
            shipping_postal_code="01000",
        )

        with self.assertRaises(ValidationError):
            OrderBaseValidator.validate_contact(order)


class OrderAthleteValidatorTests(TestCase):
    """Tests para OrderAthleteValidator"""

    def test_validate_athlete_personal_order_owner(self):
        """En orden PERSONAL, solo el dueño puede ser atleta"""
        order = OrderFactory(order_type="PERSONAL")
        athlete = order.owner_user

        # No debe lanzar excepción
        OrderAthleteValidator.validate_athlete_for_order(order, athlete)

    def test_validate_athlete_personal_order_other_user(self):
        """En orden PERSONAL, otro usuario no puede ser atleta"""
        order = OrderFactory(order_type="PERSONAL")
        other_athlete = AthleteFactory()

        with self.assertRaises(ValidationError):
            OrderAthleteValidator.validate_athlete_for_order(order, other_athlete)

    def test_validate_athlete_team_order_member(self):
        """En orden TEAM, atleta debe ser miembro activo"""
        team = TeamFactory()
        athlete = AthleteFactory()
        UserTeamMembershipFactory(
            team=team,
            user=athlete,
            role_in_team="ATHLETE",
            status="accepted",
            is_active=True,
        )

        order = TeamOrderFactory(owner_team=team)

        # No debe lanzar excepción
        OrderAthleteValidator.validate_athlete_for_order(order, athlete)

    def test_validate_athlete_team_order_non_member(self):
        """En orden TEAM, atleta NO miembro falla"""
        team = TeamFactory()
        other_athlete = AthleteFactory()  # No está en el equipo

        order = TeamOrderFactory(owner_team=team)

        with self.assertRaises(ValidationError):
            OrderAthleteValidator.validate_athlete_for_order(order, other_athlete)

    def test_validate_athlete_team_order_inactive_member(self):
        """Atleta inactivo en equipo no es válido"""
        team = TeamFactory()
        athlete = AthleteFactory()
        UserTeamMembershipFactory(
            team=team,
            user=athlete,
            role_in_team="ATHLETE",
            status="accepted",
            is_active=False,  # INACTIVO
        )

        order = TeamOrderFactory(owner_team=team)

        with self.assertRaises(ValidationError):
            OrderAthleteValidator.validate_athlete_for_order(order, athlete)

    def test_validate_not_duplicated_passes(self):
        """No hay error si atleta no está duplicado"""
        product = ProductWithMeasurementsFactory()
        item = OrderItemFactory(product=product)
        athlete = AthleteFactory()

        # No debe lanzar excepción
        OrderAthleteValidator.validate_not_duplicated(item, athlete)

    def test_validate_not_duplicated_fails(self):
        product = ProductWithMeasurementsFactory()

        team = TeamFactory()
        order = TeamOrderFactory(owner_team=team)

        item = OrderItemFactory(order=order, product=product)

        athlete = AthleteFactory()
        UserTeamMembershipFactory(team=team, user=athlete, role_in_team="ATHLETE")

        # primera asignación válida
        OrderItemAthleteFactory(order_item=item, athlete=athlete)

        # ahora sí test real
        with self.assertRaises(ValidationError):
            OrderAthleteValidator.validate_not_duplicated(item, athlete)


class OrderDesignValidatorTests(TestCase):
    """Tests para OrderDesignValidator"""

    def test_validate_no_items(self):
        """Falla si no hay items"""
        order = OrderFactory()

        with self.assertRaises(ValidationError):
            OrderDesignValidator.validate(order)

    def test_validate_no_designs(self):
        """Falla si no hay diseños"""
        order = OrderFactory()
        product = ProductFactory(usage_type="TEAM_CUSTOM")
        OrderItemFactory(order=order, product=product)

        with self.assertRaises(ValidationError):
            OrderDesignValidator.validate(order)

    def test_validate_no_final_design(self):
        """Falla si no hay diseño marcado como final"""
        from orders.tests.factories import OrderDesignImageFactory

        order = OrderFactory()
        product = ProductFactory(usage_type="TEAM_CUSTOM")
        OrderItemFactory(order=order, product=product)

        OrderDesignImageFactory(order=order, is_final=False)

        with self.assertRaises(ValidationError):
            OrderDesignValidator.validate(order)

    def test_validate_with_final_design(self):
        """Pasa si hay diseño final"""
        from orders.tests.factories import OrderDesignImageFactory

        order = OrderFactory()
        product = ProductFactory(usage_type="TEAM_CUSTOM")
        OrderItemFactory(order=order, product=product)

        OrderDesignImageFactory(order=order, is_final=True)

        # No debe lanzar excepción
        OrderDesignValidator.validate(order)


class OrderMeasurementsValidatorTests(TestCase):
    """Tests para OrderMeasurementsValidator"""

    def test_validate_complete_all_measurements_present(self):
        """Pasa si todas las medidas están completas"""
        from orders.tests.factories import OrderItemMeasurementFactory

        team = TeamFactory()
        order = TeamOrderFactory(owner_team=team)

        product = ProductWithMeasurementsFactory()
        item = OrderItemFactory(order=order, product=product)

        athlete = AthleteFactory()
        UserTeamMembershipFactory(team=team, user=athlete, role_in_team="ATHLETE")

        athlete_item = OrderItemAthleteFactory(order_item=item, athlete=athlete)

        # Crear todas las medidas requeridas
        for pmf in product.measurement_fields.filter(required=True):
            OrderItemMeasurementFactory(
                athlete_item=athlete_item, field=pmf.field, value="100"
            )

        # No debe lanzar excepción
        OrderMeasurementsValidator.validate_complete(order)

    def test_validate_complete_missing_measurements(self):
        """Falla si faltan medidas"""
        team = TeamFactory()
        order = TeamOrderFactory(owner_team=team)

        product = ProductWithMeasurementsFactory()
        item = OrderItemFactory(order=order, product=product)

        athlete = AthleteFactory()
        UserTeamMembershipFactory(team=team, user=athlete, role_in_team="ATHLETE")

        athlete_item = OrderItemAthleteFactory(order_item=item, athlete=athlete)
        # NO crear medidas

        with self.assertRaises(ValidationError):
            OrderMeasurementsValidator.validate_complete(order)


class OrderContactValidatorTests(TestCase):
    """Tests para OrderContactValidator"""

    def test_validate_complete_all_fields_present(self):
        """Pasa si todos los campos están completos"""
        order = OrderFactory()
        OrderContactInfoFactory(order=order)

        # No debe lanzar excepción
        OrderContactValidator.validate_complete(order)

    def test_validate_complete_missing_name(self):
        """Falla si falta nombre"""
        order = OrderFactory()
        OrderContactInfoFactory(order=order, contact_name="")

        with self.assertRaises(ValidationError):
            OrderContactValidator.validate_complete(order)

    def test_validate_complete_missing_multiple_fields(self):
        """Falla si faltan múltiples campos"""
        order = OrderFactory()
        OrderContactInfoFactory(
            order=order, contact_name="", contact_phone="", shipping_city=""
        )

        with self.assertRaises(ValidationError) as cm:
            OrderContactValidator.validate_complete(order)

        # Debe mencionar los campos faltantes
        error_msg = str(cm.exception)
        self.assertIn("Nombre", error_msg)
        self.assertIn("Teléfono", error_msg)
        self.assertIn("Ciudad", error_msg)

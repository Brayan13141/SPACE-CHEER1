from decimal import Decimal
from django.test import TestCase
from django.core.exceptions import ValidationError
from orders.models import OrderItemAthlete

from orders.tests.factories import (
    OrderFactory,
    TeamOrderFactory,
    OrderItemFactory,
    OrderItemAthleteFactory,
    OrderItemMeasurementFactory,
    ProductFactory,
    ProductWithSizesFactory,
    ProductWithMeasurementsFactory,
    AthleteFactory,
    TeamFactory,
    UserTeamMembershipFactory,
    OrderContactInfoFactory,
)
from orders.models import Order


class OrderModelTests(TestCase):
    """Tests para el modelo Order"""

    def test_order_creation_personal_valid(self):
        """Orden PERSONAL con owner_user válida"""
        order = OrderFactory(order_type="PERSONAL")
        self.assertEqual(order.status, "DRAFT")
        self.assertIsNotNone(order.owner_user)
        self.assertIsNone(order.owner_team)

    def test_order_creation_team_valid(self):
        """Orden TEAM con owner_team válida"""
        order = TeamOrderFactory()
        self.assertEqual(order.order_type, "TEAM")
        self.assertIsNone(order.owner_user)
        self.assertIsNotNone(order.owner_team)

    def test_order_personal_cannot_have_team(self):
        """Orden PERSONAL no puede tener owner_team"""
        team = TeamFactory()
        with self.assertRaises(ValidationError) as cm:
            OrderFactory(order_type="PERSONAL", owner_team=team)
        self.assertIn("PERSONAL", str(cm.exception))

    def test_order_team_cannot_have_user(self):
        """Orden TEAM no puede tener owner_user"""
        user = AthleteFactory()
        with self.assertRaises(ValidationError) as cm:
            order = Order(
                order_type="TEAM", owner_user=user, owner_team=None, created_by=user
            )
            order.full_clean()
        self.assertIn("TEAM", str(cm.exception))

    def test_order_type_immutable(self):
        """No se puede cambiar order_type después de crear"""
        order = OrderFactory(order_type="PERSONAL")
        order.save()

        order.order_type = "TEAM"
        with self.assertRaises(ValidationError):
            order.save()

    def test_order_total_calculation(self):
        """Cálculo correcto del total"""
        order = OrderFactory()

        product1 = ProductFactory(base_price=Decimal("50.00"))
        product2 = ProductFactory(base_price=Decimal("100.00"))

        OrderItemFactory(order=order, product=product1, quantity=2)
        OrderItemFactory(order=order, product=product2, quantity=1)

        self.assertEqual(order.total, Decimal("200.00"))

    def test_order_can_edit_general_draft(self):
        """Orden en DRAFT es editable"""
        order = OrderFactory(status="DRAFT")
        self.assertTrue(order.can_edit_general())

    def test_order_can_edit_measurements_open(self):
        """Medidas editables cuando measurements_open=True"""
        order = OrderFactory(
            status="DRAFT", measurements_open=True, measurements_locked=False
        )
        self.assertTrue(order.can_edit_measurements())

    def test_order_cannot_edit_measurements_locked(self):
        """Medidas no editables cuando locked=True"""
        order = OrderFactory(
            status="DRAFT", measurements_open=True, measurements_locked=True
        )
        self.assertFalse(order.can_edit_measurements())

    def test_order_requires_design_detection(self):
        """Detecta correctamente si requiere diseño"""
        order = OrderFactory()
        product_custom = ProductWithMeasurementsFactory()
        OrderItemFactory(order=order, product=product_custom)

        self.assertTrue(order.requires_design)

    def test_order_status_change_requires_service(self):
        """No se puede cambiar status directamente"""
        order = OrderFactory(status="DRAFT")
        order.status = "PENDING"

        with self.assertRaises(ValidationError):
            order.save()


class OrderItemModelTests(TestCase):
    """Tests para OrderItem"""

    def test_item_price_calculation(self):
        """Precio unitario calcula base + talla"""
        product = ProductWithSizesFactory()
        size = product.size_variants.first()
        size.additional_price = Decimal("10.00")
        size.save()

        item = OrderItemFactory(product=product, size_variant=size, quantity=2)

        expected_unit = product.base_price + Decimal("10.00")
        self.assertEqual(item.unit_price, expected_unit)
        self.assertEqual(item.subtotal, expected_unit * 2)

    def test_item_requires_size_for_standard_strategy(self):
        """Producto STANDARD requiere talla"""
        product = ProductWithSizesFactory()

        with self.assertRaises(ValidationError):
            OrderItemFactory(product=product, size_variant=None)

    def test_item_cannot_change_size_after_creation(self):
        """No se puede cambiar talla después de crear"""
        product = ProductWithSizesFactory()
        size1 = product.size_variants.first()
        size2 = product.size_variants.last()

        item = OrderItemFactory(product=product, size_variant=size1)
        item.size_variant = size2

        with self.assertRaises(ValidationError):
            item.save()

    def test_item_configuration_state_incomplete_no_athletes(self):
        """Estado INCOMPLETE si requiere atletas y no tiene"""
        product = ProductWithMeasurementsFactory()
        item = OrderItemFactory(product=product)

        self.assertEqual(item.configuration_state, "INCOMPLETE")

    def test_item_configuration_state_ready(self):
        """Estado READY cuando todo está configurado"""
        product = ProductFactory(usage_type="GLOBAL", size_strategy="NONE")
        item = OrderItemFactory(product=product)

        self.assertEqual(item.configuration_state, "READY")


class OrderItemAthleteModelTests(TestCase):
    """Tests para OrderItemAthlete"""

    def test_athlete_assignment_team_order_valid(self):
        """Asignar atleta válido a orden TEAM"""
        team = TeamFactory()
        athlete = AthleteFactory()
        UserTeamMembershipFactory(
            team=team, user=athlete, role_in_team="ATHLETE", status="accepted"
        )

        order = TeamOrderFactory(owner_team=team)
        product = ProductWithMeasurementsFactory()
        item = OrderItemFactory(order=order, product=product)

        athlete_item = OrderItemAthleteFactory(order_item=item, athlete=athlete)
        self.assertIsNotNone(athlete_item.pk)

    def test_athlete_assignment_team_order_invalid_athlete(self):
        """No se puede asignar atleta que no pertenece al equipo"""
        team = TeamFactory()
        other_athlete = AthleteFactory()  # No está en el equipo

        order = TeamOrderFactory(owner_team=team)
        product = ProductWithMeasurementsFactory()
        item = OrderItemFactory(order=order, product=product)

        with self.assertRaises(ValidationError):
            athlete_item = OrderItemAthlete(order_item=item, athlete=other_athlete)
            athlete_item.full_clean()

    def test_athlete_has_complete_measurements_true(self):
        """Detecta medidas completas correctamente"""

        product = ProductWithMeasurementsFactory()

        order = TeamOrderFactory()
        item = OrderItemFactory(order=order, product=product)

        athlete = AthleteFactory()
        UserTeamMembershipFactory(
            team=order.owner_team,
            user=athlete,
            role_in_team="ATHLETE",
            status="accepted",
        )

        athlete_item = OrderItemAthleteFactory(
            order_item=item,
            athlete=athlete,
        )

        # Crear todos los campos requeridos
        for pmf in product.measurement_fields.filter(required=True):
            OrderItemMeasurementFactory(
                athlete_item=athlete_item,
                field=pmf.field,
                value="100",
            )

        self.assertTrue(athlete_item.has_complete_measurements())

    def test_athlete_has_complete_measurements_false(self):
        product = ProductWithMeasurementsFactory()

        order = TeamOrderFactory()  # 🔥 clave
        item = OrderItemFactory(order=order, product=product)

        athlete = AthleteFactory()
        UserTeamMembershipFactory(
            team=order.owner_team,
            user=athlete,
            role_in_team="ATHLETE",
            status="accepted",
        )

        athlete_item = OrderItemAthleteFactory(
            order_item=item,
            athlete=athlete,
        )

        self.assertFalse(athlete_item.has_complete_measurements())


class OrderContactInfoModelTests(TestCase):
    """Tests para OrderContactInfo"""

    def test_contact_info_validation_all_fields_required(self):
        """Todos los campos son requeridos"""
        contact = OrderContactInfoFactory(
            contact_name="",
            contact_phone="",
            contact_email="test@test.com",
            shipping_address_line="",
            shipping_city="",
            shipping_postal_code="",
        )

        with self.assertRaises(ValidationError) as cm:
            contact.full_clean()

        errors = cm.exception.message_dict
        # Debería tener errores en los campos vacíos
        self.assertTrue(len(errors) > 0)

    def test_contact_info_cannot_edit_when_closed(self):
        """No se puede editar cuando closed=True"""
        contact = OrderContactInfoFactory(closed=False)
        contact.save()

        # Simular que ya está cerrado en DB
        contact.closed = True
        contact.save()

        # Intentar modificar
        contact.contact_name = "Nuevo Nombre"
        with self.assertRaises(ValidationError):
            contact.save()


# ============================================================
# TESTS DE VALIDACIONES CRUZADAS
# ============================================================


class OrderValidationTests(TestCase):
    """Tests de validaciones complejas"""

    def test_order_validate_ready_missing_contact(self):
        """Orden no está lista si falta contacto"""
        order = OrderFactory()
        OrderItemFactory(order=order)

        with self.assertRaises(ValidationError):
            Order.validate_order_ready(order)

    def test_order_validate_ready_missing_items(self):
        """Orden no está lista sin items"""
        order = OrderFactory()
        OrderContactInfoFactory(order=order)

        with self.assertRaises(ValidationError):
            Order.validate_order_ready(order)

    def test_order_validate_ready_incomplete_measurements(self):
        """Orden no está lista si faltan medidas"""
        order = TeamOrderFactory()
        OrderContactInfoFactory(order=order)

        product = ProductWithMeasurementsFactory()
        item = OrderItemFactory(order=order, product=product)

        athlete = AthleteFactory()
        UserTeamMembershipFactory(
            team=order.owner_team, user=athlete, role_in_team="ATHLETE"
        )

        athlete_item = OrderItemAthleteFactory(order_item=item, athlete=athlete)
        # No crear medidas

        with self.assertRaises(ValidationError):
            Order.validate_order_ready(order)

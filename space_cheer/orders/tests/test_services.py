from django.test import TestCase
from django.core.exceptions import ValidationError, PermissionDenied
from django.utils import timezone
from decimal import Decimal

from orders.tests.factories import (
    OrderFactory,
    TeamOrderFactory,
    OrderItemFactory,
    OrderItemAthleteFactory,
    OrderItemMeasurementFactory,
    ProductFactory,
    ProductWithMeasurementsFactory,
    ProductSizeVariantFactory,
    AthleteFactory,
    CoachFactory,
    UserFactory,
    TeamFactory,
    UserTeamMembershipFactory,
    OrderContactInfoFactory,
    OrderDesignImageFactory,
)
from orders.services.state import OrderStateService, OrderCreationService
from orders.models import Order, OrderLog


class OrderCreationServiceTests(TestCase):
    """Tests para OrderCreationService"""

    def test_create_personal_order_valid(self):
        """Crear orden personal válida"""
        user = UserFactory()

        order = OrderCreationService.create_order(
            order_type="PERSONAL", created_by=user, owner_user=user, owner_team=None
        )

        self.assertEqual(order.order_type, "PERSONAL")
        self.assertEqual(order.status, "DRAFT")
        self.assertEqual(order.owner_user, user)
        self.assertIsNone(order.owner_team)

    def test_create_team_order_valid(self):
        """Crear orden de equipo válida"""
        team = TeamFactory()
        coach = team.coach

        order = OrderCreationService.create_order(
            order_type="TEAM", created_by=coach, owner_user=None, owner_team=team
        )

        self.assertEqual(order.order_type, "TEAM")
        self.assertEqual(order.owner_team, team)
        self.assertIsNone(order.owner_user)

    def test_create_order_logs_creation(self):
        """Se crea un log al crear orden"""
        user = UserFactory()

        order = OrderCreationService.create_order(
            order_type="PERSONAL", created_by=user, owner_user=user
        )

        logs = OrderLog.objects.filter(order=order, action="ORDER_CREATED")
        self.assertEqual(logs.count(), 1)


class OrderStateTransitionTests(TestCase):
    """Tests para transiciones de estado"""

    def setUp(self):
        """Setup común para tests de transiciones"""
        self.user = UserFactory()
        self.order = OrderFactory(created_by=self.user, owner_user=self.user)
        OrderContactInfoFactory(order=self.order)

    def test_transition_draft_to_pending_valid(self):
        """Transición DRAFT → PENDING válida"""
        product = ProductFactory()
        OrderItemFactory(order=self.order, product=product)

        order = OrderStateService.transition(
            order=self.order, to_status="PENDING", user=self.user
        )

        self.assertEqual(order.status, "PENDING")

    def test_transition_draft_to_pending_requires_items(self):
        """DRAFT → PENDING requiere items"""
        with self.assertRaises(ValidationError):
            OrderStateService.transition(
                order=self.order, to_status="PENDING", user=self.user
            )

    def test_transition_draft_to_pending_custom_requires_freeze_payment(self):
        team = TeamFactory()
        self.order = TeamOrderFactory(owner_team=team)
        self.user = team.coach
        OrderContactInfoFactory(order=self.order)

        product = ProductWithMeasurementsFactory()
        item = OrderItemFactory(order=self.order, product=product)

        athlete = AthleteFactory()
        UserTeamMembershipFactory(team=team, user=athlete, role_in_team="ATLETA")

        athlete_item = OrderItemAthleteFactory(order_item=item, athlete=athlete)

        for pmf in product.measurement_fields.all():
            OrderItemMeasurementFactory(
                athlete_item=athlete_item, field=pmf.field, value="100"
            )

        with self.assertRaises(ValidationError) as cm:
            OrderStateService.transition(
                order=self.order, to_status="PENDING", user=self.user
            )

        self.assertIn("congel", str(cm.exception).lower())

    def test_transition_pending_to_design_approved_requires_design(self):
        """DESIGN_APPROVED requiere imagen de diseño final"""
        product = ProductFactory(usage_type="TEAM_CUSTOM")
        OrderItemFactory(order=self.order, product=product)
        self.order.status = "PENDING"
        self.order.freeze_payment_date = timezone.now()
        self.order._allow_status_change = True
        self.order.save()

        with self.assertRaises(ValidationError):
            OrderStateService.transition(
                order=self.order, to_status="DESIGN_APPROVED", user=self.user
            )

    def test_transition_pending_to_design_approved_valid(self):
        team = TeamFactory()
        self.order = TeamOrderFactory(owner_team=team)

        admin = UserFactory(is_superuser=True)

        OrderContactInfoFactory(order=self.order)

        product = ProductFactory(usage_type="TEAM_CUSTOM")
        item = OrderItemFactory(order=self.order, product=product)

        athlete = AthleteFactory()
        UserTeamMembershipFactory(team=team, user=athlete, role_in_team="ATLETA")

        athlete_item = OrderItemAthleteFactory(order_item=item, athlete=athlete)

        # 🔥 completar medidas (esto faltaba)
        for pmf in product.measurement_fields.all():
            OrderItemMeasurementFactory(
                athlete_item=athlete_item, field=pmf.field, value="100"
            )

        self.order.status = "PENDING"
        self.order.freeze_payment_date = timezone.now()
        self.order._allow_status_change = True
        self.order.save()

        OrderDesignImageFactory(order=self.order, is_final=True)

        order = OrderStateService.transition(
            order=self.order,
            to_status="DESIGN_APPROVED",
            user=admin,
        )

        self.assertEqual(order.status, "DESIGN_APPROVED")

    def test_transition_design_approved_to_production_requires_dates(self):
        product = ProductFactory(usage_type="TEAM_CUSTOM", product_type="UNIFORM")
        OrderItemFactory(order=self.order, product=product)

        admin = UserFactory(is_superuser=True)

        OrderDesignImageFactory(order=self.order, is_final=True)
        self.order.measurements_locked = True
        self.order.locked_at = timezone.now()
        self.order.status = "DESIGN_APPROVED"
        self.order._allow_status_change = True
        self.order.save()

        with self.assertRaises(ValidationError) as cm:
            OrderStateService.transition(
                order=self.order,
                to_status="IN_PRODUCTION",
                user=admin,
            )

        error_msg = str(cm.exception).lower()
        print("Error message:", error_msg)  # Debug: imprimir mensaje de error
        self.assertTrue(
            "fecha" in error_msg or "pago" in error_msg or "entrega" in error_msg
        )

    def test_transition_creates_log(self):
        """Cada transición crea un log"""
        product = ProductFactory()
        OrderItemFactory(order=self.order, product=product)

        OrderStateService.transition(
            order=self.order, to_status="PENDING", user=self.user
        )

        log = OrderLog.objects.filter(
            order=self.order, from_status="DRAFT", to_status="PENDING"
        ).first()

        self.assertIsNotNone(log)
        self.assertEqual(log.user, self.user)

    def test_transition_invalid_not_allowed(self):
        """No se permite transición no válida"""
        self.order.status = "DELIVERED"
        self.order._allow_status_change = True
        self.order.save()

        with self.assertRaises(ValidationError):
            OrderStateService.transition(
                order=self.order, to_status="DRAFT", user=self.user
            )

    def test_transition_permission_denied_for_non_owner(self):
        """Usuario sin permisos no puede hacer transición"""
        other_user = UserFactory()
        product = ProductFactory()
        OrderItemFactory(order=self.order, product=product)

        with self.assertRaises(PermissionDenied):
            OrderStateService.transition(
                order=self.order, to_status="PENDING", user=other_user
            )


class OrderStateTransitionMeasurementsTests(TestCase):
    """Tests de transiciones con medidas"""

    def test_design_approved_closes_measurements(self):
        """DESIGN_APPROVED cierra medidas automáticamente"""
        admin = UserFactory(is_superuser=True)

        team = TeamFactory()
        order = TeamOrderFactory(owner_team=team)
        OrderContactInfoFactory(order=order)

        product = ProductWithMeasurementsFactory()
        item = OrderItemFactory(order=order, product=product)

        athlete = AthleteFactory()
        UserTeamMembershipFactory(team=team, user=athlete, role_in_team="ATLETA")

        athlete_item = OrderItemAthleteFactory(order_item=item, athlete=athlete)

        # Crear medidas completas
        for pmf in product.measurement_fields.all():
            OrderItemMeasurementFactory(
                athlete_item=athlete_item, field=pmf.field, value="100"
            )

        order.status = "PENDING"
        order.freeze_payment_date = timezone.now()
        order._allow_status_change = True
        order.save()

        OrderDesignImageFactory(order=order, is_final=True)

        order = OrderStateService.transition(
            order=order, to_status="DESIGN_APPROVED", user=admin
        )

        self.assertFalse(order.measurements_open)

    def test_in_production_locks_measurements(self):
        """IN_PRODUCTION bloquea medidas definitivamente"""
        admin = UserFactory(is_superuser=True)

        team = TeamFactory()
        order = TeamOrderFactory(owner_team=team)
        OrderContactInfoFactory(order=order)

        product = ProductWithMeasurementsFactory()
        item = OrderItemFactory(order=order, product=product)

        athlete = AthleteFactory()
        UserTeamMembershipFactory(team=team, user=athlete, role_in_team="ATLETA")
        athlete_item = OrderItemAthleteFactory(order_item=item, athlete=athlete)

        for pmf in product.measurement_fields.all():
            OrderItemMeasurementFactory(
                athlete_item=athlete_item, field=pmf.field, value="100"
            )

        order.status = "DESIGN_APPROVED"
        order.measurements_due_date = timezone.now().date()
        order.uniform_delivery_date = timezone.now().date()
        order.first_payment_date = timezone.now()
        order._allow_status_change = True
        order.measurements_locked = True
        order.locked_at = timezone.now()
        order.save()

        OrderDesignImageFactory(order=order, is_final=True)

        order = OrderStateService.transition(
            order=order, to_status="IN_PRODUCTION", user=admin
        )

        self.assertTrue(order.measurements_locked)
        self.assertIsNotNone(order.locked_at)

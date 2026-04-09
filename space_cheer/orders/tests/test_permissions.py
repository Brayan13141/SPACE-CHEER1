from django.test import TestCase
from django.contrib.auth import get_user_model

from orders.tests.factories import (
    OrderFactory,
    TeamOrderFactory,
    UserFactory,
    AthleteFactory,
    CoachFactory,
    TeamFactory,
    UserTeamMembershipFactory,
    RoleFactory,
)
from orders.permissions import OrderPermissions, can_manage_order, can_approve_design
from accounts.models import UserOwnership

User = get_user_model()


class OrderPermissionsManageTests(TestCase):
    """Tests para can_manage_order"""

    def test_superuser_can_manage_any_order(self):
        """Superuser puede gestionar cualquier orden"""
        superuser = UserFactory(is_superuser=True)
        order = OrderFactory()

        self.assertTrue(OrderPermissions.can_manage_order(superuser, order))

    def test_admin_can_manage_any_order(self):
        """Admin puede gestionar cualquier orden"""
        admin = UserFactory()
        admin_role = RoleFactory(name="ADMIN")
        admin.roles.add(admin_role)

        order = OrderFactory()

        self.assertTrue(OrderPermissions.can_manage_order(admin, order))

    def test_creator_can_manage_own_order(self):
        """Creador puede gestionar su propia orden"""
        user = UserFactory()
        order = OrderFactory(created_by=user, owner_user=user)

        self.assertTrue(OrderPermissions.can_manage_order(user, order))

    def test_owner_can_manage_personal_order(self):
        """Dueño puede gestionar orden PERSONAL"""
        user = UserFactory()
        order = OrderFactory(order_type="PERSONAL", owner_user=user)

        self.assertTrue(OrderPermissions.can_manage_order(user, order))

    def test_coach_can_manage_owned_user_order(self):
        """Coach puede gestionar órdenes de usuarios bajo su propiedad"""
        coach = CoachFactory()
        athlete = AthleteFactory()

        UserOwnership.objects.create(owner=coach, user=athlete, is_active=True)

        order = OrderFactory(order_type="PERSONAL", owner_user=athlete)

        self.assertTrue(OrderPermissions.can_manage_order(coach, order))

    def test_headcoach_can_manage_team_order(self):
        """HEADCOACH puede gestionar órdenes de su equipo"""
        team = TeamFactory()
        coach = team.coach

        order = TeamOrderFactory(owner_team=team)

        self.assertTrue(OrderPermissions.can_manage_order(coach, order))

    def test_staff_member_can_manage_team_order(self):
        """STAFF del equipo puede gestionar órdenes"""
        team = TeamFactory()
        staff = UserFactory()

        UserTeamMembershipFactory(
            team=team,
            user=staff,
            role_in_team="STAFF",
            status="accepted",
            is_active=True,
        )

        order = TeamOrderFactory(owner_team=team)

        self.assertTrue(OrderPermissions.can_manage_order(staff, order))

    def test_athlete_cannot_manage_team_order(self):
        """Atleta NO puede gestionar órdenes del equipo"""
        team = TeamFactory()
        athlete = AthleteFactory()

        UserTeamMembershipFactory(
            team=team,
            user=athlete,
            role_in_team="ATLETA",
            status="accepted",
            is_active=True,
        )

        order = TeamOrderFactory(owner_team=team)

        self.assertFalse(OrderPermissions.can_manage_order(athlete, order))

    def test_unrelated_user_cannot_manage_order(self):
        """Usuario sin relación no puede gestionar orden"""
        user = UserFactory()
        order = OrderFactory()

        self.assertFalse(OrderPermissions.can_manage_order(user, order))


class OrderPermissionsApproveDesignTests(TestCase):
    """Tests para can_approve_design"""

    def test_admin_can_approve_design(self):
        """Admin puede aprobar diseños"""
        admin = UserFactory()
        admin_role = RoleFactory(name="ADMIN")
        admin.roles.add(admin_role)

        order = OrderFactory()

        self.assertTrue(OrderPermissions.can_approve_design(admin, order))

    def test_owner_can_approve_personal_order_design(self):
        """Dueño puede aprobar diseño de orden personal"""
        user = UserFactory()
        order = OrderFactory(order_type="PERSONAL", owner_user=user)

        self.assertTrue(OrderPermissions.can_approve_design(user, order))

    def test_headcoach_can_approve_team_order_design(self):
        """HEADCOACH puede aprobar diseño de orden de equipo"""
        team = TeamFactory()
        coach = team.coach

        UserTeamMembershipFactory(
            team=team,
            user=coach,
            role_in_team="HEADCOACH",
            status="accepted",
            is_active=True,
        )

        order = TeamOrderFactory(owner_team=team)

        self.assertTrue(OrderPermissions.can_approve_design(coach, order))

    def test_regular_coach_cannot_approve_team_design(self):
        """COACH regular no puede aprobar diseño (solo HEADCOACH)"""
        team = TeamFactory()
        coach = UserFactory()

        UserTeamMembershipFactory(
            team=team,
            user=coach,
            role_in_team="COACH",  # No HEADCOACH
            status="accepted",
            is_active=True,
        )

        order = TeamOrderFactory(owner_team=team)

        self.assertFalse(OrderPermissions.can_approve_design(coach, order))

    def test_staff_cannot_approve_design(self):
        """STAFF no puede aprobar diseños"""
        team = TeamFactory()
        staff = UserFactory()

        UserTeamMembershipFactory(
            team=team,
            user=staff,
            role_in_team="STAFF",
            status="accepted",
            is_active=True,
        )

        order = TeamOrderFactory(owner_team=team)

        self.assertFalse(OrderPermissions.can_approve_design(staff, order))


class OrderPermissionsCancelTests(TestCase):
    """Tests para can_cancel_order"""

    def test_can_cancel_draft_order(self):
        """Se puede cancelar orden en DRAFT"""
        user = UserFactory()
        order = OrderFactory(status="DRAFT", created_by=user, owner_user=user)

        self.assertTrue(OrderPermissions.can_cancel_order(user, order))

    def test_can_cancel_pending_order(self):
        """Se puede cancelar orden en PENDING"""
        user = UserFactory()
        order = OrderFactory(created_by=user, owner_user=user)

        order._allow_status_change = True
        order.status = "PENDING"
        order.save()

        self.assertTrue(OrderPermissions.can_cancel_order(user, order))

    def test_cannot_cancel_delivered_order(self):
        """NO se puede cancelar orden DELIVERED"""
        user = UserFactory()
        order = OrderFactory(created_by=user, owner_user=user)
        order._allow_status_change = True
        order.status = "DELIVERED"
        order.save()

        self.assertFalse(OrderPermissions.can_cancel_order(user, order))

    def test_cannot_cancel_in_production_order(self):
        """NO se puede cancelar orden IN_PRODUCTION"""
        user = UserFactory()
        order = OrderFactory(created_by=user, owner_user=user)
        order._allow_status_change = True
        order.status = "IN_PRODUCTION"
        order.save()

        self.assertFalse(OrderPermissions.can_cancel_order(user, order))

    def set_order_status(order, status):
        order._allow_status_change = True
        order.status = status
        order.save()
        return order


class OrderPermissionsViewTests(TestCase):
    """Tests para can_view_order"""

    def test_admin_can_view_any_order(self):
        """Admin puede ver cualquier orden"""
        admin = UserFactory()
        admin_role = RoleFactory(name="ADMIN")
        admin.roles.add(admin_role)

        order = OrderFactory()

        self.assertTrue(OrderPermissions.can_view_order(admin, order))

    def test_team_member_can_view_team_order(self):
        """Miembro del equipo puede ver órdenes del equipo"""
        team = TeamFactory()
        athlete = AthleteFactory()

        UserTeamMembershipFactory(
            team=team,
            user=athlete,
            role_in_team="ATLETA",
            status="accepted",
            is_active=True,
        )

        order = TeamOrderFactory(owner_team=team)

        self.assertTrue(OrderPermissions.can_view_order(athlete, order))

    def test_owner_can_view_personal_order(self):
        """Dueño puede ver su orden personal"""
        user = UserFactory()
        order = OrderFactory(order_type="PERSONAL", owner_user=user)

        self.assertTrue(OrderPermissions.can_view_order(user, order))

    def test_coach_can_view_owned_user_order(self):
        """Coach puede ver órdenes de usuarios bajo su propiedad"""
        coach = CoachFactory()
        athlete = AthleteFactory()

        UserOwnership.objects.create(owner=coach, user=athlete, is_active=True)

        order = OrderFactory(order_type="PERSONAL", owner_user=athlete)

        self.assertTrue(OrderPermissions.can_view_order(coach, order))

    def test_unrelated_user_cannot_view_order(self):
        """Usuario sin relación no puede ver orden"""
        user = UserFactory()
        order = OrderFactory()

        self.assertFalse(OrderPermissions.can_view_order(user, order))

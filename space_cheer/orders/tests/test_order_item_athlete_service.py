# orders/tests/test_order_item_athlete_service.py
"""
F6 (hallazgo 4.2): import_from_team hacía un no-op silencioso ("No había
cambios para aplicar.") cuando el roster del equipo estaba en status
"pending" — sin ninguna pista de la causa real para el coach.
"""

import pytest
from django.test import TestCase

from orders.services.servicesItems.order_item_athlete_service import (
    OrderItemAthleteService,
)
from orders.tests.factories import (
    AthleteFactory,
    CoachFactory,
    OrderItemFactory,
    ProductWithMeasurementsFactory,
    TeamFactory,
    TeamOrderFactory,
    UserTeamMembershipFactory,
)


@pytest.mark.django_db
class ImportFromTeamPendingMembershipTests(TestCase):
    def setUp(self):
        self.coach = CoachFactory()
        self.team = TeamFactory(coach=self.coach)
        self.order = TeamOrderFactory(owner_team=self.team, created_by=self.coach)
        self.product = ProductWithMeasurementsFactory(usage_type="TEAM_CUSTOM")
        self.item = OrderItemFactory(order=self.order, product=self.product)

    def test_pending_memberships_reported_as_no_op_reason(self):
        athlete = AthleteFactory()
        UserTeamMembershipFactory(
            user=athlete,
            team=self.team,
            role_in_team="ATHLETE",
            status="pending",
            is_active=True,
        )

        result = OrderItemAthleteService.import_from_team(self.item)

        self.assertEqual(result["created"], 0)
        self.assertEqual(result["updated"], 0)
        self.assertTrue(
            any("pendiente" in err.lower() for err in result["errors"]),
            result["errors"],
        )

    def test_no_pending_no_athletes_no_extra_message(self):
        result = OrderItemAthleteService.import_from_team(self.item)

        self.assertEqual(result["created"], 0)
        self.assertEqual(result["errors"], [])

from django.test import TestCase

from orders.tests.factories import (
    UserFactory, RoleFactory, TeamFactory, UserTeamMembershipFactory,
)
from accounts.services.permission_service import AccountPermissions


class CanReviewRequestsTests(TestCase):
    def setUp(self):
        self.team = TeamFactory()  # coach = HEADCOACH dueño
        self.coach = UserFactory()
        self.coach.roles.add(RoleFactory(name="COACH"))
        UserTeamMembershipFactory(
            user=self.coach, team=self.team, role_in_team="COACH",
            status="accepted", is_active=True,
        )

    def test_headcoach_owner_can_review(self):
        self.assertTrue(AccountPermissions.can_review_requests(self.team.coach, self.team))

    def test_accepted_coach_can_review(self):
        self.assertTrue(AccountPermissions.can_review_requests(self.coach, self.team))

    def test_outsider_cannot_review(self):
        outsider = UserFactory()
        outsider.roles.add(RoleFactory(name="COACH"))
        self.assertFalse(AccountPermissions.can_review_requests(outsider, self.team))

    def test_coach_cannot_manage_team(self):
        self.assertFalse(AccountPermissions.can_manage_team(self.coach, self.team))

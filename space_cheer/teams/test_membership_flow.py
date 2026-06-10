from unittest.mock import patch
from django.test import TestCase, Client
from django.core import mail
from django.urls import reverse

from django.core.exceptions import ValidationError

from orders.tests.factories import (
    UserFactory, RoleFactory, TeamFactory, AthleteFactory, UserTeamMembershipFactory,
)
from teams.models import UserTeamMembership
from accounts.models import UserOwnership, CoachProfile, Role


class JoinNotificationTaskTests(TestCase):
    def test_join_request_email_to_coach(self):
        from accounts.tasks import notify_team_join_request
        team = TeamFactory()
        team.coach.email = "hc@test.com"
        team.coach.save(update_fields=["email"])
        athlete = AthleteFactory()
        m = UserTeamMembershipFactory(
            user=athlete, team=team, role_in_team="ATHLETE",
            status="pending", is_active=False,
        )
        notify_team_join_request(m.id)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("hc@test.com", mail.outbox[0].to)

    def test_decision_email_to_athlete(self):
        from accounts.tasks import notify_join_decision
        athlete = AthleteFactory(email="a@test.com")
        team = TeamFactory()
        m = UserTeamMembershipFactory(
            user=athlete, team=team, role_in_team="ATHLETE",
            status="accepted", is_active=True,
        )
        notify_join_decision(m.id, True)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("a@test.com", mail.outbox[0].to)


class RequestJoinByCodeTests(TestCase):
    def setUp(self):
        self.team = TeamFactory()
        self.athlete = AthleteFactory()

    @patch("teams.services.membership_service.notify_team_join_request")
    def test_valid_code_creates_pending(self, mock_notify):
        from teams.services.membership_service import MembershipService
        m = MembershipService.request_join_by_code(user=self.athlete, code=self.team.join_code)
        self.assertEqual(m.status, "pending")
        self.assertFalse(m.is_active)
        self.assertEqual(m.role_in_team, "ATHLETE")
        mock_notify.delay.assert_called_once_with(m.id)

    @patch("teams.services.membership_service.notify_team_join_request")
    def test_code_is_case_insensitive(self, mock_notify):
        from teams.services.membership_service import MembershipService
        m = MembershipService.request_join_by_code(user=self.athlete, code=self.team.join_code.lower())
        self.assertEqual(m.team, self.team)

    @patch("teams.services.membership_service.notify_team_join_request")
    def test_invalid_code_raises(self, mock_notify):
        from teams.services.membership_service import MembershipService
        with self.assertRaises(ValidationError):
            MembershipService.request_join_by_code(user=self.athlete, code="ZZZZZZ")

    @patch("teams.services.membership_service.notify_team_join_request")
    def test_duplicate_pending_raises(self, mock_notify):
        from teams.services.membership_service import MembershipService
        MembershipService.request_join_by_code(user=self.athlete, code=self.team.join_code)
        with self.assertRaises(ValidationError):
            MembershipService.request_join_by_code(user=self.athlete, code=self.team.join_code)

    @patch("teams.services.membership_service.notify_team_join_request")
    def test_already_member_raises(self, mock_notify):
        from teams.services.membership_service import MembershipService
        UserTeamMembershipFactory(
            user=self.athlete, team=self.team, role_in_team="ATHLETE",
            status="accepted", is_active=True,
        )
        with self.assertRaises(ValidationError):
            MembershipService.request_join_by_code(user=self.athlete, code=self.team.join_code)


class AcceptRejectRequestTests(TestCase):
    def setUp(self):
        self.team = TeamFactory()
        self.athlete = AthleteFactory()
        self.membership = UserTeamMembershipFactory(
            user=self.athlete, team=self.team, role_in_team="ATHLETE",
            status="pending", is_active=False,
        )

    @patch("teams.services.membership_service.notify_join_decision")
    def test_accept_activates_and_creates_ownership(self, mock_notify):
        from teams.services.membership_service import MembershipService
        MembershipService.accept_request(membership=self.membership, by=self.team.coach)
        self.membership.refresh_from_db()
        self.assertEqual(self.membership.status, "accepted")
        self.assertTrue(self.membership.is_active)
        self.assertTrue(
            UserOwnership.objects.filter(
                owner=self.team.coach, user=self.athlete, is_active=True
            ).exists()
        )
        mock_notify.delay.assert_called_once_with(self.membership.id, True)

    @patch("teams.services.membership_service.notify_join_decision")
    def test_reject_sets_rejected(self, mock_notify):
        from teams.services.membership_service import MembershipService
        MembershipService.reject_request(membership=self.membership, by=self.team.coach)
        self.membership.refresh_from_db()
        self.assertEqual(self.membership.status, "rejected")
        self.assertFalse(self.membership.is_active)
        mock_notify.delay.assert_called_once_with(self.membership.id, False)


class RemoveMemberTests(TestCase):
    def setUp(self):
        self.team = TeamFactory()
        self.athlete = AthleteFactory()
        self.membership = UserTeamMembershipFactory(
            user=self.athlete, team=self.team, role_in_team="ATHLETE",
            status="accepted", is_active=True,
        )
        UserOwnership.objects.create(owner=self.team.coach, user=self.athlete, is_active=True)

    def test_remove_athlete_deactivates_membership_and_ownership(self):
        from teams.services.membership_service import MembershipService
        MembershipService.remove_member(membership=self.membership, removed_by=self.team.coach)
        self.membership.refresh_from_db()
        self.assertFalse(self.membership.is_active)
        self.assertEqual(self.membership.status, "inactive")
        self.assertFalse(
            UserOwnership.objects.filter(
                owner=self.team.coach, user=self.athlete, is_active=True
            ).exists()
        )

    def test_remove_coach_keeps_global_role(self):
        from teams.services.membership_service import MembershipService
        coach = UserFactory()
        coach.roles.add(RoleFactory(name="COACH"))
        coach_m = UserTeamMembershipFactory(
            user=coach, team=self.team, role_in_team="COACH",
            status="accepted", is_active=True,
        )
        MembershipService.remove_member(membership=coach_m, removed_by=self.team.coach)
        coach_m.refresh_from_db()
        self.assertFalse(coach_m.is_active)
        self.assertTrue(coach.roles.filter(name="COACH").exists())


class AddCoachMemberTests(TestCase):
    def setUp(self):
        self.team = TeamFactory()
        Role.objects.get_or_create(name="COACH", defaults={"is_coach_type": True})

    def test_add_coach_grants_global_role_and_approves(self):
        from teams.services.membership_service import MembershipService
        user = UserFactory()  # sin rol coach
        MembershipService.add_member(team=self.team, user=user, role="COACH", added_by=self.team.coach)
        self.assertTrue(user.roles.filter(name="COACH").exists())
        profile = CoachProfile.objects.get(user=user)
        self.assertEqual(profile.approval_status, CoachProfile.APPROVED)

    def test_add_athlete_does_not_grant_coach_role(self):
        from teams.services.membership_service import MembershipService
        user = UserFactory()
        MembershipService.add_member(team=self.team, user=user, role="ATHLETE", added_by=self.team.coach)
        self.assertFalse(user.roles.filter(name="COACH").exists())


class JoinByCodeViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.team = TeamFactory()
        self.athlete = AthleteFactory(profile_completed=True)

    @patch("teams.services.membership_service.notify_team_join_request")
    def test_athlete_can_post_code(self, mock_notify):
        self.client.force_login(self.athlete)
        resp = self.client.post(reverse("teams:join_by_code"), {"code": self.team.join_code})
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(
            UserTeamMembership.objects.filter(
                user=self.athlete, team=self.team, status="pending"
            ).exists()
        )

    @patch("teams.services.membership_service.notify_team_join_request")
    def test_invalid_code_shows_message_no_membership(self, mock_notify):
        self.client.force_login(self.athlete)
        resp = self.client.post(reverse("teams:join_by_code"), {"code": "BADCOD"})
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(UserTeamMembership.objects.filter(user=self.athlete).exists())


class AcceptRejectRemoveEndpointTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.team = TeamFactory()
        self.team.coach.profile_completed = True
        self.team.coach.save(update_fields=["profile_completed"])
        self.athlete = AthleteFactory(profile_completed=True)
        self.pending = UserTeamMembershipFactory(
            user=self.athlete, team=self.team, role_in_team="ATHLETE",
            status="pending", is_active=False,
        )

    @patch("teams.services.membership_service.notify_join_decision")
    def test_headcoach_accepts(self, mock_notify):
        self.client.force_login(self.team.coach)
        resp = self.client.post(reverse("teams:accept_request", args=[self.pending.id]))
        self.assertEqual(resp.status_code, 302)
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, "accepted")

    @patch("teams.services.membership_service.notify_join_decision")
    def test_accepted_coach_can_accept(self, mock_notify):
        coach = UserFactory(profile_completed=True)
        coach.roles.add(RoleFactory(name="COACH"))
        UserTeamMembershipFactory(
            user=coach, team=self.team, role_in_team="COACH",
            status="accepted", is_active=True,
        )
        self.client.force_login(coach)
        resp = self.client.post(reverse("teams:accept_request", args=[self.pending.id]))
        self.assertEqual(resp.status_code, 302)
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, "accepted")

    @patch("teams.services.membership_service.notify_join_decision")
    def test_outsider_cannot_accept(self, mock_notify):
        outsider = UserFactory(profile_completed=True)
        outsider.roles.add(RoleFactory(name="COACH"))
        self.client.force_login(outsider)
        resp = self.client.post(reverse("teams:accept_request", args=[self.pending.id]))
        self.assertIn(resp.status_code, (403, 302, 404))
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, "pending")

    def test_headcoach_removes_member(self):
        active = UserTeamMembershipFactory(
            user=AthleteFactory(), team=self.team, role_in_team="ATHLETE",
            status="accepted", is_active=True,
        )
        self.client.force_login(self.team.coach)
        resp = self.client.post(reverse("teams:remove_member", args=[active.id]))
        self.assertEqual(resp.status_code, 302)
        active.refresh_from_db()
        self.assertFalse(active.is_active)

    def test_coach_cannot_remove_member(self):
        coach = UserFactory(profile_completed=True)
        coach.roles.add(RoleFactory(name="COACH"))
        UserTeamMembershipFactory(
            user=coach, team=self.team, role_in_team="COACH",
            status="accepted", is_active=True,
        )
        active = UserTeamMembershipFactory(
            user=AthleteFactory(), team=self.team, role_in_team="ATHLETE",
            status="accepted", is_active=True,
        )
        self.client.force_login(coach)
        resp = self.client.post(reverse("teams:remove_member", args=[active.id]))
        self.assertIn(resp.status_code, (403, 302, 404))
        active.refresh_from_db()
        self.assertTrue(active.is_active)


class CoachTeamsViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.team = TeamFactory()
        self.coach = UserFactory(profile_completed=True)
        self.coach.roles.add(RoleFactory(name="COACH"))
        UserTeamMembershipFactory(
            user=self.coach, team=self.team, role_in_team="COACH",
            status="accepted", is_active=True,
        )

    def test_coach_sees_own_team(self):
        self.client.force_login(self.coach)
        resp = self.client.get(reverse("teams:coach_teams"))
        self.assertEqual(resp.status_code, 200)
        self.assertIn(self.team, [it["team"] for it in resp.context["items"]])

    def test_coach_does_not_see_other_teams(self):
        other_team = TeamFactory()
        self.client.force_login(self.coach)
        resp = self.client.get(reverse("teams:coach_teams"))
        self.assertNotIn(other_team, [it["team"] for it in resp.context["items"]])

    def test_athlete_redirected(self):
        athlete = AthleteFactory(profile_completed=True)
        self.client.force_login(athlete)
        resp = self.client.get(reverse("teams:coach_teams"))
        self.assertEqual(resp.status_code, 302)

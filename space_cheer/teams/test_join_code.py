from unittest.mock import patch
from django.test import TestCase, Client
from django.urls import reverse

from orders.tests.factories import TeamFactory, UserFactory, RoleFactory
from teams.models import Team


class JoinCodeGenerationTests(TestCase):
    def test_assigns_code_on_create(self):
        team = TeamFactory()
        self.assertTrue(team.join_code)
        self.assertEqual(len(team.join_code), 6)

    def test_retries_on_collision(self):
        """Si el primer código colisiona, debe reintentar y no lanzar."""
        team1 = TeamFactory()
        with patch("teams.models.secrets.token_hex", side_effect=[team1.join_code[:6].lower(), "abcdef"]):
            team2 = TeamFactory()
        self.assertEqual(team2.join_code, "ABCDEF")


class RegenerateJoinCodeTests(TestCase):
    def test_regenerate_changes_code(self):
        from teams.services.team_service import TeamService
        team = TeamFactory()
        old = team.join_code
        TeamService.regenerate_join_code(team)
        team.refresh_from_db()
        self.assertNotEqual(team.join_code, old)
        self.assertEqual(len(team.join_code), 6)

    def test_regenerate_is_unique(self):
        from teams.services.team_service import TeamService
        team_a = TeamFactory()
        team_b = TeamFactory()
        TeamService.regenerate_join_code(team_b)
        team_b.refresh_from_db()
        self.assertNotEqual(team_b.join_code, team_a.join_code)


class RegenerateCodeViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.team = TeamFactory()  # team.coach es HEADCOACH (CoachFactory)
        self.team.coach.profile_completed = True
        self.team.coach.save(update_fields=["profile_completed"])

    def test_headcoach_owner_can_regenerate(self):
        old = self.team.join_code
        self.client.force_login(self.team.coach)
        resp = self.client.post(reverse("teams:regenerate_code", args=[self.team.id]))
        self.assertEqual(resp.status_code, 302)
        self.team.refresh_from_db()
        self.assertNotEqual(self.team.join_code, old)

    def test_non_owner_forbidden(self):
        intruder = UserFactory(profile_completed=True)
        intruder.roles.add(RoleFactory(name="HEADCOACH"))
        self.client.force_login(intruder)
        resp = self.client.post(reverse("teams:regenerate_code", args=[self.team.id]))
        self.assertIn(resp.status_code, (403, 302, 404))
        old = self.team.join_code
        self.team.refresh_from_db()
        self.assertEqual(self.team.join_code, old)

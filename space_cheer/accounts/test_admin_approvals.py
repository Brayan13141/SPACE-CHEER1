from unittest.mock import patch

from django.test import TestCase, Client
from django.urls import reverse

from orders.tests.factories import UserFactory, RoleFactory
from accounts.models import CoachProfile
from accounts.services.coach_approval_service import CoachApprovalService


def make_admin():
    user = UserFactory(is_superuser=True, is_staff=True, profile_completed=True)
    return user


def make_pending_headcoach():
    hc = UserFactory(profile_completed=True)
    hc.roles.add(RoleFactory(name="HEADCOACH"))
    CoachApprovalService.submit_headcoach(hc)
    return hc, CoachProfile.objects.get(user=hc)


class HeadcoachApprovalsViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = make_admin()

    def test_list_requires_admin(self):
        hc, _ = make_pending_headcoach()
        # El headcoach pendiente está inactivo: no puede loguear; probamos un atleta cualquiera
        other = UserFactory(profile_completed=True)
        other.roles.add(RoleFactory(name="ATHLETE"))
        self.client.force_login(other)
        resp = self.client.get(reverse("accounts:headcoach_approvals"))
        self.assertEqual(resp.status_code, 302)

    def test_admin_sees_pending(self):
        hc, _ = make_pending_headcoach()
        self.client.force_login(self.admin)
        resp = self.client.get(reverse("accounts:headcoach_approvals"))
        self.assertEqual(resp.status_code, 200)
        self.assertIn(hc, resp.context["pending"])

    @patch("accounts.tasks.notify_headcoach_approved")
    def test_approve_activates(self, mock_notify):
        hc, profile = make_pending_headcoach()
        self.client.force_login(self.admin)
        self.client.post(
            reverse("accounts:headcoach_approvals"),
            {"action": "approve", "profile_id": profile.pk},
        )
        hc.refresh_from_db()
        profile.refresh_from_db()
        self.assertTrue(hc.is_active)
        self.assertEqual(profile.approval_status, CoachProfile.APPROVED)

    def test_reject_keeps_inactive(self):
        hc, profile = make_pending_headcoach()
        self.client.force_login(self.admin)
        self.client.post(
            reverse("accounts:headcoach_approvals"),
            {"action": "reject", "profile_id": profile.pk, "reason": "Falta documentación"},
        )
        hc.refresh_from_db()
        profile.refresh_from_db()
        self.assertFalse(hc.is_active)
        self.assertEqual(profile.approval_status, CoachProfile.REJECTED)

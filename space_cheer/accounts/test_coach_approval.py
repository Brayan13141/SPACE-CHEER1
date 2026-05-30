from unittest.mock import patch
from django.test import TestCase
from django.core import mail

from django.test import Client
from django.urls import reverse

from orders.tests.factories import UserFactory, RoleFactory
from accounts.models import CoachProfile
from accounts.utils.redirect_flow import get_user_redirect_flow


class NotifyHeadcoachApprovedTaskTests(TestCase):
    def test_sends_email_to_headcoach(self):
        from accounts.tasks import notify_headcoach_approved
        user = UserFactory(email="hc@test.com")
        notify_headcoach_approved(user.id)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("hc@test.com", mail.outbox[0].to)

    def test_skips_when_no_email(self):
        from accounts.tasks import notify_headcoach_approved
        user = UserFactory()
        user.email = ""
        user.save(update_fields=["email"])
        notify_headcoach_approved(user.id)
        self.assertEqual(len(mail.outbox), 0)


class CoachApprovalServiceTests(TestCase):
    def setUp(self):
        self.admin = UserFactory()
        self.headcoach = UserFactory()
        self.headcoach.roles.add(RoleFactory(name="HEADCOACH"))
        self.profile = CoachProfile.objects.get(user=self.headcoach)

    def test_submit_sets_inactive(self):
        from accounts.services.coach_approval_service import CoachApprovalService
        CoachApprovalService.submit_headcoach(self.headcoach)
        self.headcoach.refresh_from_db()
        self.assertFalse(self.headcoach.is_active)

    @patch("accounts.tasks.notify_headcoach_approved")
    def test_approve_activates_and_marks_approved(self, mock_notify):
        from accounts.services.coach_approval_service import CoachApprovalService
        CoachApprovalService.submit_headcoach(self.headcoach)
        CoachApprovalService.approve_headcoach(self.profile, by=self.admin)
        self.headcoach.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertTrue(self.headcoach.is_active)
        self.assertEqual(self.profile.approval_status, CoachProfile.APPROVED)
        self.assertIsNotNone(self.profile.approved_at)

    @patch("accounts.tasks.notify_headcoach_approved")
    def test_approve_fires_notification(self, mock_notify):
        from accounts.services.coach_approval_service import CoachApprovalService
        CoachApprovalService.approve_headcoach(self.profile, by=self.admin)
        mock_notify.delay.assert_called_once_with(self.headcoach.id)

    def test_reject_keeps_inactive_with_reason(self):
        from accounts.services.coach_approval_service import CoachApprovalService
        CoachApprovalService.submit_headcoach(self.headcoach)
        CoachApprovalService.reject_headcoach(self.profile, by=self.admin, reason="Sin certificación")
        self.headcoach.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertFalse(self.headcoach.is_active)
        self.assertEqual(self.profile.approval_status, CoachProfile.REJECTED)
        self.assertEqual(self.profile.rejection_reason, "Sin certificación")


class ProfileSetupHeadcoachTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.hc_role = RoleFactory(name="HEADCOACH")  # allow_dashboard_access=True por defecto

    def test_headcoach_setup_deactivates_account(self):
        user = UserFactory()  # activo, sin rol, profile_completed=False
        self.client.force_login(user)
        resp = self.client.post(
            reverse("accounts:profile_setup"),
            {"role": self.hc_role.pk, "first_name": "Ana", "last_name": "Lopez"},
        )
        user.refresh_from_db()
        self.assertFalse(user.is_active)
        self.assertTemplateUsed(resp, "account/headcoach_pending.html")


class RedirectFlowGateTests(TestCase):
    def test_coach_pending_is_not_trapped(self):
        """Un COACH con CoachProfile PENDING NO debe ser redirigido a la pantalla de pendiente."""
        user = UserFactory(profile_completed=True)
        user.roles.add(RoleFactory(name="COACH"))  # signal crea CoachProfile PENDING
        url = get_user_redirect_flow(user)
        self.assertNotIn("pending", url)
        self.assertNotIn("rejected", url)

    def test_headcoach_pending_is_gated(self):
        user = UserFactory(profile_completed=True)
        user.roles.add(RoleFactory(name="HEADCOACH"))
        url = get_user_redirect_flow(user)
        self.assertIn(reverse("accounts:coach_pending_approval"), url)

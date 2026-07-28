from django.test import TestCase, Client
from django.urls import reverse

from accounts.models import Notification
from orders.tests.factories import UserFactory


class ManagementNotificationsListTests(TestCase):
    """La campana de 'gestión' del navbar (asignación de tarea, job listo,
    error reportado) contaba notificaciones pero no tenía ninguna pantalla
    donde el usuario pudiera realmente verlas — a diferencia de las
    notificaciones sociales (social:notifications)."""

    def setUp(self):
        self.client = Client()
        self.user = UserFactory(profile_completed=True)
        self.other_user = UserFactory(profile_completed=True)

    def test_unauthenticated_redirects_to_login(self):
        response = self.client.get(reverse("accounts:notifications"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response["Location"])

    def test_shows_only_own_non_social_notifications(self):
        mine = Notification.objects.create(
            user=self.user,
            title="Nueva tarea asignada",
            notification_type=Notification.NotificationType.TASK_ASSIGNED,
        )
        Notification.objects.create(
            user=self.other_user,
            title="Tarea de otro usuario",
            notification_type=Notification.NotificationType.TASK_ASSIGNED,
        )
        Notification.objects.create(
            user=self.user,
            title="Like a tu publicación",
            notification_type=Notification.NotificationType.SOCIAL_LIKE,
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse("accounts:notifications"))
        shown = list(response.context["page_obj"])
        self.assertEqual(shown, [mine])


class ManagementNotificationReadTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.user = UserFactory(profile_completed=True)
        self.other_user = UserFactory(profile_completed=True)
        self.notification = Notification.objects.create(
            user=self.user,
            title="Job de producción #1 listo",
            notification_type=Notification.NotificationType.JOB_READY,
        )

    def test_mark_read_sets_read_true(self):
        self.client.force_login(self.user)
        url = reverse("accounts:notification_read", kwargs={"pk": self.notification.pk})
        self.client.post(url)
        self.notification.refresh_from_db()
        self.assertTrue(self.notification.read)

    def test_cannot_mark_another_users_notification(self):
        self.client.force_login(self.other_user)
        url = reverse("accounts:notification_read", kwargs={"pk": self.notification.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)
        self.notification.refresh_from_db()
        self.assertFalse(self.notification.read)

    def test_mark_all_read_only_affects_own_non_social(self):
        social = Notification.objects.create(
            user=self.user,
            title="Comentario en tu publicación",
            notification_type=Notification.NotificationType.SOCIAL_COMMENT,
        )
        others = Notification.objects.create(
            user=self.other_user,
            title="Tarea de otro usuario",
            notification_type=Notification.NotificationType.TASK_ASSIGNED,
        )
        self.client.force_login(self.user)
        self.client.post(reverse("accounts:notifications_read_all"))

        self.notification.refresh_from_db()
        social.refresh_from_db()
        others.refresh_from_db()
        self.assertTrue(self.notification.read)
        self.assertFalse(social.read)
        self.assertFalse(others.read)

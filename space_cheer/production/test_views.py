from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse, NoReverseMatch
from django.utils import timezone

from accounts.models import Role
from orders.tests.factories import OrderFactory, OrderItemFactory, UserFactory

User = get_user_model()
from production.models import (
    ProductionStage,
    ProductStageConfig,
    ProductionJob,
    ProductionTask,
    ProductionRole,
    OperarioRoleAssignment,
    StageResponsibility,
)
from production.services import ProductionJobService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_operario():
    role, _ = Role.objects.get_or_create(
        name="OPERARIO", defaults={"is_production_type": True}
    )
    user = UserFactory(profile_completed=True)
    user.roles.add(role)
    return user, role


def make_superuser():
    user = UserFactory(is_superuser=True, is_staff=True, profile_completed=True)
    return user


def make_stage(name="Diseño", slug="diseno", order=1):
    return ProductionStage.objects.create(
        name=name, slug=slug, display_order=order
    )


# ---------------------------------------------------------------------------
# Operario — dashboard
# ---------------------------------------------------------------------------

class OperarioDashboardTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.operario, self.op_role = make_operario()
        self.stage = make_stage()

        self.order = OrderFactory()
        self.item = OrderItemFactory(order=self.order)
        ProductStageConfig.objects.create(
            product=self.item.product, stage=self.stage, display_order=1
        )
        with patch("production.services.notify_production_stage_complete"):
            ProductionJobService.create_for_order(self.order)
        self.job = ProductionJob.objects.get(order=self.order)
        self.task = self.job.tasks.first()

        prod_role = ProductionRole.objects.create(
            name="Diseñador", created_by=self.operario
        )
        prod_role.stages.add(self.stage)
        OperarioRoleAssignment.objects.create(
            user=self.operario, role=prod_role, assigned_by=self.operario
        )

    def test_unauthenticated_redirects_to_login(self):
        response = self.client.get(reverse("production:dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response["Location"])

    def test_wrong_role_redirects(self):
        other = UserFactory(profile_completed=True)
        other_role, _ = Role.objects.get_or_create(name="COACH")
        other.roles.add(other_role)
        self.client.force_login(other)
        response = self.client.get(reverse("production:dashboard"))
        self.assertEqual(response.status_code, 302)

    def test_operario_gets_200(self):
        self.client.force_login(self.operario)
        response = self.client.get(reverse("production:dashboard"))
        self.assertEqual(response.status_code, 200)

    def test_dashboard_shows_pending_tasks_for_operario(self):
        self.client.force_login(self.operario)
        response = self.client.get(reverse("production:dashboard"))
        self.assertIn(self.task, response.context["tasks"])

    def test_dashboard_empty_state_without_production_roles(self):
        """OPERARIO sin ProductionRoles asignados ve mensaje vacío"""
        operario_bare, _ = make_operario()
        self.client.force_login(operario_bare)
        response = self.client.get(reverse("production:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["tasks"]), 0)


# ---------------------------------------------------------------------------
# Operario — task_complete
# ---------------------------------------------------------------------------

class TaskCompleteTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.operario, _ = make_operario()
        self.stage = make_stage()
        order = OrderFactory()
        item = OrderItemFactory(order=order)
        ProductStageConfig.objects.create(
            product=item.product, stage=self.stage, display_order=1
        )
        with patch("production.services.notify_production_stage_complete"):
            ProductionJobService.create_for_order(order)
        self.job = ProductionJob.objects.get(order=order)
        self.task = self.job.tasks.first()
        # El operario necesita un rol de producción que cubra la etapa
        prod_role = ProductionRole.objects.create(name="TestRole")
        prod_role.stages.add(self.stage)
        OperarioRoleAssignment.objects.create(
            user=self.operario, role=prod_role, assigned_by=self.operario
        )
        self.task.assigned_to = self.operario
        self.task.save(update_fields=["assigned_to"])

    @patch("production.services.notify_production_stage_complete")
    def test_post_completes_task(self, mock_notify):
        self.client.force_login(self.operario)
        url = reverse("production:task_complete", kwargs={"pk": self.task.pk})
        started_at = self.job.created_at.strftime("%Y-%m-%dT%H:%M")
        self.client.post(url, {"started_at": started_at, "notes": ""})
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, "COMPLETED")

    @patch("production.services.notify_production_stage_complete")
    def test_post_redirects_after_complete(self, mock_notify):
        self.client.force_login(self.operario)
        url = reverse("production:task_complete", kwargs={"pk": self.task.pk})
        started_at = self.job.created_at.strftime("%Y-%m-%dT%H:%M")
        response = self.client.post(url, {"started_at": started_at, "notes": ""})
        self.assertEqual(response.status_code, 302)

    def test_unauthenticated_redirects(self):
        url = reverse("production:task_complete", kwargs={"pk": self.task.pk})
        response = self.client.post(url, {})
        self.assertEqual(response.status_code, 302)


# ---------------------------------------------------------------------------
# Admin — admin_overview
# ---------------------------------------------------------------------------

class AdminOverviewTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin = make_superuser()
        self.stage = make_stage()
        order = OrderFactory()
        item = OrderItemFactory(order=order)
        ProductStageConfig.objects.create(
            product=item.product, stage=self.stage, display_order=1
        )
        with patch("production.services.notify_production_stage_complete"):
            ProductionJobService.create_for_order(order)

    def test_admin_gets_200(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("production:admin_overview"))
        self.assertEqual(response.status_code, 200)

    def test_unauthenticated_redirects(self):
        response = self.client.get(reverse("production:admin_overview"))
        self.assertEqual(response.status_code, 302)

    def test_operario_is_redirected(self):
        operario, _ = make_operario()
        self.client.force_login(operario)
        response = self.client.get(reverse("production:admin_overview"))
        self.assertEqual(response.status_code, 302)

    def test_context_has_stats(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("production:admin_overview"))
        self.assertIn("stats", response.context)

    def test_context_has_jobs(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("production:admin_overview"))
        self.assertIn("jobs", response.context)


# ---------------------------------------------------------------------------
# Admin — admin_job_detail
# ---------------------------------------------------------------------------

class AdminJobDetailTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin = make_superuser()
        stage = make_stage()
        order = OrderFactory()
        item = OrderItemFactory(order=order)
        ProductStageConfig.objects.create(
            product=item.product, stage=stage, display_order=1
        )
        with patch("production.services.notify_production_stage_complete"):
            ProductionJobService.create_for_order(order)
        self.job = ProductionJob.objects.get(order=order)

    def test_admin_gets_200(self):
        self.client.force_login(self.admin)
        url = reverse("production:admin_job_detail", kwargs={"pk": self.job.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_context_has_job(self):
        self.client.force_login(self.admin)
        url = reverse("production:admin_job_detail", kwargs={"pk": self.job.pk})
        response = self.client.get(url)
        self.assertEqual(response.context["job"], self.job)

    def test_context_has_items_without_tasks_for_unconfigured_product(self):
        """F8 (hallazgo 4.4): un item cuyo producto no tiene etapas
        configuradas no genera ninguna task — el admin debe verlo en el
        detalle del job, no solo en un warning de logs."""
        from orders.tests.factories import ProductFactory

        order = OrderFactory()
        configured_item = OrderItemFactory(order=order)
        stage = make_stage(name="Corte", slug="corte-f8", order=1)
        ProductStageConfig.objects.create(
            product=configured_item.product, stage=stage, display_order=1
        )
        unconfigured_product = ProductFactory(usage_type="GLOBAL", size_strategy="NONE")
        unconfigured_item = OrderItemFactory(order=order, product=unconfigured_product)

        with patch("production.services.notify_production_stage_complete"):
            job = ProductionJobService.create_for_order(order)

        self.client.force_login(self.admin)
        url = reverse("production:admin_job_detail", kwargs={"pk": job.pk})
        response = self.client.get(url)

        self.assertIn(unconfigured_item, response.context["items_without_tasks"])
        self.assertNotIn(configured_item, response.context["items_without_tasks"])


# ---------------------------------------------------------------------------
# Admin — toggle_urgent
# ---------------------------------------------------------------------------

class ToggleUrgentTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin = make_superuser()
        stage = make_stage()
        order = OrderFactory()
        item = OrderItemFactory(order=order)
        ProductStageConfig.objects.create(
            product=item.product, stage=stage, display_order=1
        )
        with patch("production.services.notify_production_stage_complete"):
            ProductionJobService.create_for_order(order)
        self.job = ProductionJob.objects.get(order=order)

    def test_toggle_sets_urgent_true(self):
        self.client.force_login(self.admin)
        url = reverse("production:toggle_urgent", kwargs={"pk": self.job.pk})
        self.client.post(url)
        self.job.refresh_from_db()
        self.assertTrue(self.job.is_urgent)

    def test_toggle_twice_returns_to_false(self):
        self.client.force_login(self.admin)
        url = reverse("production:toggle_urgent", kwargs={"pk": self.job.pk})
        self.client.post(url)
        self.client.post(url)
        self.job.refresh_from_db()
        self.assertFalse(self.job.is_urgent)

    def test_redirects_after_toggle(self):
        self.client.force_login(self.admin)
        url = reverse("production:toggle_urgent", kwargs={"pk": self.job.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)


# ---------------------------------------------------------------------------
# Admin — assign_task
# ---------------------------------------------------------------------------

class AssignTaskTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin = make_superuser()
        self.operario, _ = make_operario()
        stage = make_stage()
        order = OrderFactory()
        item = OrderItemFactory(order=order)
        ProductStageConfig.objects.create(
            product=item.product, stage=stage, display_order=1
        )
        with patch("production.services.notify_production_stage_complete"):
            ProductionJobService.create_for_order(order)
        self.task = ProductionTask.objects.first()

    @patch("production.tasks.notify_task_assigned")
    def test_assign_task_sets_assigned_to(self, mock_notify):
        self.client.force_login(self.admin)
        url = reverse("production:assign_task", kwargs={"pk": self.task.pk})
        self.client.post(url, {"operario_id": self.operario.pk})
        self.task.refresh_from_db()
        self.assertEqual(self.task.assigned_to, self.operario)

    @patch("production.tasks.notify_task_assigned")
    def test_redirects_after_assign(self, mock_notify):
        self.client.force_login(self.admin)
        url = reverse("production:assign_task", kwargs={"pk": self.task.pk})
        response = self.client.post(url, {"operario_id": self.operario.pk})
        self.assertEqual(response.status_code, 302)


# ---------------------------------------------------------------------------
# Config — manage_stages
# ---------------------------------------------------------------------------

class ManageStagesTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin = make_superuser()

    def test_admin_gets_200(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("production:manage_stages"))
        self.assertEqual(response.status_code, 200)

    def test_post_creates_stage(self):
        self.client.force_login(self.admin)
        self.client.post(
            reverse("production:manage_stages"),
            {"name": "Corte", "slug": "corte", "display_order": 5, "icon": "✂️"},
        )
        self.assertTrue(ProductionStage.objects.filter(slug="corte").exists())

    def test_unauthenticated_redirects(self):
        response = self.client.get(reverse("production:manage_stages"))
        self.assertEqual(response.status_code, 302)


# ---------------------------------------------------------------------------
# Config — manage_roles
# ---------------------------------------------------------------------------

class ManageRolesTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin = make_superuser()
        self.stage = make_stage()

    def test_admin_gets_200(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("production:manage_roles"))
        self.assertEqual(response.status_code, 200)

    def test_post_creates_production_role(self):
        self.client.force_login(self.admin)
        self.client.post(
            reverse("production:manage_roles"),
            {"name": "Diseñador", "stages": [self.stage.pk]},
        )
        self.assertTrue(ProductionRole.objects.filter(name="Diseñador").exists())

    def test_edit_updates_name_and_stages(self):
        self.client.force_login(self.admin)
        role = ProductionRole.objects.create(name="Original", created_by=self.admin)
        other_stage = make_stage(name="Archivos", slug="archivos", order=2)
        self.client.post(
            reverse("production:manage_roles"),
            {"role_id": role.pk, "name": "Renombrado", "stages": [other_stage.pk]},
        )
        role.refresh_from_db()
        self.assertEqual(role.name, "Renombrado")
        self.assertEqual(list(role.stages.all()), [other_stage])

    def test_create_rejects_duplicate_name_case_insensitive(self):
        self.client.force_login(self.admin)
        ProductionRole.objects.create(name="Diseñador", created_by=self.admin)
        self.client.post(
            reverse("production:manage_roles"),
            {"name": "diseñador", "stages": []},
        )
        self.assertEqual(
            ProductionRole.objects.filter(name__iexact="diseñador").count(), 1
        )

    def test_edit_rejects_duplicate_name(self):
        self.client.force_login(self.admin)
        role_a = ProductionRole.objects.create(name="Cone", created_by=self.admin)
        role_b = ProductionRole.objects.create(name="Chino", created_by=self.admin)
        self.client.post(
            reverse("production:manage_roles"),
            {"role_id": role_b.pk, "name": "Cone", "stages": []},
        )
        role_b.refresh_from_db()
        self.assertEqual(role_b.name, "Chino")

    def test_delete_role_without_blockers_succeeds(self):
        self.client.force_login(self.admin)
        role = ProductionRole.objects.create(name="Sobrante", created_by=self.admin)
        self.client.post(
            reverse("production:manage_roles"),
            {"action": "delete", "role_id": role.pk},
        )
        self.assertFalse(ProductionRole.objects.filter(pk=role.pk).exists())

    def test_delete_blocked_when_operarios_assigned(self):
        self.client.force_login(self.admin)
        role = ProductionRole.objects.create(name="Cone", created_by=self.admin)
        operario, _ = make_operario()
        OperarioRoleAssignment.objects.create(
            user=operario, role=role, assigned_by=self.admin
        )
        self.client.post(
            reverse("production:manage_roles"),
            {"action": "delete", "role_id": role.pk},
        )
        self.assertTrue(ProductionRole.objects.filter(pk=role.pk).exists())

    def test_delete_blocked_when_responsible_for_stage(self):
        self.client.force_login(self.admin)
        role = ProductionRole.objects.create(name="Costurero", created_by=self.admin)
        StageResponsibility.objects.create(stage=self.stage, responsible_role=role)
        self.client.post(
            reverse("production:manage_roles"),
            {"action": "delete", "role_id": role.pk},
        )
        self.assertTrue(ProductionRole.objects.filter(pk=role.pk).exists())

    def test_role_with_operarios_shows_disabled_delete(self):
        self.client.force_login(self.admin)
        role = ProductionRole.objects.create(name="Cone", created_by=self.admin)
        operario, _ = make_operario()
        OperarioRoleAssignment.objects.create(
            user=operario, role=role, assigned_by=self.admin
        )
        response = self.client.get(reverse("production:manage_roles"))
        self.assertContains(response, "No se puede eliminar")

    def test_role_without_blockers_shows_delete_form(self):
        self.client.force_login(self.admin)
        role = ProductionRole.objects.create(name="Libre", created_by=self.admin)
        response = self.client.get(reverse("production:manage_roles"))
        self.assertContains(response, f'id="delRole{role.pk}"')

    def test_role_edit_collapse_present(self):
        self.client.force_login(self.admin)
        role = ProductionRole.objects.create(name="Editable", created_by=self.admin)
        response = self.client.get(reverse("production:manage_roles"))
        self.assertContains(response, f'id="editRole{role.pk}"')


# ---------------------------------------------------------------------------
# Config — manage_operarios
# ---------------------------------------------------------------------------

class ManageOperariosTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin = make_superuser()
        self.op_role, _ = Role.objects.get_or_create(
            name="OPERARIO", defaults={"is_production_type": True}
        )

    def test_admin_gets_200(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("production:manage_operarios"))
        self.assertEqual(response.status_code, 200)

    def test_non_admin_redirected(self):
        operario, _ = make_operario()
        self.client.force_login(operario)
        response = self.client.get(reverse("production:manage_operarios"))
        self.assertEqual(response.status_code, 302)

    def test_post_creates_operario_user(self):
        self.client.force_login(self.admin)
        self.client.post(
            reverse("production:manage_operarios"),
            {
                "username": "op_nuevo",
                "first_name": "Juan",
                "last_name": "Lopez",
                "email": "juan@test.com",
                "password": "TestPass123!",
            },
        )
        user = User.objects.filter(username="op_nuevo").first()
        self.assertIsNotNone(user)
        self.assertTrue(user.profile_completed)
        self.assertTrue(user.roles.filter(name="OPERARIO").exists())

    def test_post_redirects_after_create(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("production:manage_operarios"),
            {
                "username": "op_redir",
                "first_name": "Ana",
                "last_name": "Torres",
                "email": "ana@test.com",
                "password": "TestPass123!",
            },
        )
        self.assertEqual(response.status_code, 302)

    def test_context_has_operarios(self):
        make_operario()
        self.client.force_login(self.admin)
        response = self.client.get(reverse("production:manage_operarios"))
        self.assertIn("operarios", response.context)


# ---------------------------------------------------------------------------
# Config — operario_detail (per-operario production roles)
# ---------------------------------------------------------------------------

class OperarioDetailTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin = make_superuser()
        self.operario, _ = make_operario()
        self.prod_role = ProductionRole.objects.create(
            name="Diseñador_test", created_by=self.admin
        )

    def test_admin_gets_200(self):
        self.client.force_login(self.admin)
        url = reverse("production:operario_detail", kwargs={"pk": self.operario.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_context_has_prod_roles(self):
        self.client.force_login(self.admin)
        url = reverse("production:operario_detail", kwargs={"pk": self.operario.pk})
        response = self.client.get(url)
        self.assertIn("prod_roles", response.context)

    def test_post_assigns_production_role(self):
        self.client.force_login(self.admin)
        url = reverse("production:operario_detail", kwargs={"pk": self.operario.pk})
        self.client.post(url, {"action": "assign", "role_id": self.prod_role.pk})
        self.assertTrue(
            OperarioRoleAssignment.objects.filter(
                user=self.operario, role=self.prod_role
            ).exists()
        )

    def test_post_removes_production_role(self):
        OperarioRoleAssignment.objects.create(
            user=self.operario, role=self.prod_role, assigned_by=self.admin
        )
        self.client.force_login(self.admin)
        url = reverse("production:operario_detail", kwargs={"pk": self.operario.pk})
        self.client.post(url, {"action": "remove", "role_id": self.prod_role.pk})
        self.assertFalse(
            OperarioRoleAssignment.objects.filter(
                user=self.operario, role=self.prod_role
            ).exists()
        )

    def test_non_admin_redirected(self):
        operario2, _ = make_operario()
        self.client.force_login(operario2)
        url = reverse("production:operario_detail", kwargs={"pk": self.operario.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)


# ---------------------------------------------------------------------------
# Config — manage_responsibilities (StageResponsibility)
# ---------------------------------------------------------------------------

class ManageResponsabilidadesTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin = make_superuser()
        self.stage = make_stage(name="Costura", slug="costura", order=1)
        self.role_primary = ProductionRole.objects.create(
            name="Costurero", created_by=self.admin
        )
        self.role_aux = ProductionRole.objects.create(
            name="Auxiliar Costura", created_by=self.admin
        )
        self.url = reverse("production:manage_responsibilities")

    def test_admin_gets_200(self):
        self.client.force_login(self.admin)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_unauthenticated_redirects(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_post_creates_stage_responsibility(self):
        self.client.force_login(self.admin)
        self.client.post(self.url, {
            "stage_id": self.stage.pk,
            "responsible_role_id": self.role_primary.pk,
        })
        self.assertTrue(
            StageResponsibility.objects.filter(
                stage=self.stage,
                responsible_role=self.role_primary,
            ).exists()
        )

    def test_post_with_auxiliary_roles(self):
        self.client.force_login(self.admin)
        self.client.post(self.url, {
            "stage_id": self.stage.pk,
            "responsible_role_id": self.role_primary.pk,
            "auxiliary_role_ids": [self.role_aux.pk],
        })
        resp = StageResponsibility.objects.get(stage=self.stage)
        self.assertIn(self.role_aux, resp.auxiliary_roles.all())


# ---------------------------------------------------------------------------
# Error reports
# ---------------------------------------------------------------------------

class CreateErrorReportTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin = make_superuser()
        self.stage = make_stage()
        self.responsible, _ = make_operario()
        self.client.force_login(self.admin)

    def test_post_creates_error_report_with_stage_and_responsible(self):
        from production.models import ErrorReport

        url = reverse("production:create_error_report")
        response = self.client.post(url, {
            "description": "Talla incorrecta en playera",
            "error_types": ["WRONG_SIZES"],
            "stage": self.stage.pk,
            "responsible": self.responsible.pk,
            "error_causes": ["LACK_OF_ATTENTION"],
        })
        self.assertEqual(response.status_code, 302)
        report = ErrorReport.objects.get()
        self.assertEqual(report.stage, self.stage)
        self.assertEqual(report.responsible, self.responsible)
        self.assertTrue(report.requires_reposition)

    def test_post_without_stage_or_responsible(self):
        from production.models import ErrorReport

        url = reverse("production:create_error_report")
        response = self.client.post(url, {
            "description": "Empaque incompleto",
            "error_types": [],
        })
        self.assertEqual(response.status_code, 302)
        report = ErrorReport.objects.get()
        self.assertIsNone(report.stage)
        self.assertIsNone(report.responsible)
        self.assertIsNone(report.order)

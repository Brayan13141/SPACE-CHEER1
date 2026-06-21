import logging
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.decorators import role_required
from production.models import ProductionJob, ProductionTask
from production.services import ProductionJobService

logger = logging.getLogger(__name__)
User = get_user_model()


@role_required("ADMIN", "STAFF")
def admin_overview(request):
    today = timezone.now().date()
    jobs = (
        ProductionJob.objects.select_related("order")
        .prefetch_related("tasks__stage", "tasks__assigned_to", "order__items__product")
        .annotate(
            total_tasks=Count("tasks"),
            completed_tasks=Count(
                "tasks", filter=Q(tasks__status=ProductionTask.Status.COMPLETED)
            ),
        )
        .order_by("-is_urgent", "order__uniform_delivery_date")
    )

    filter_by = request.GET.get("filter", "all")
    if filter_by == "urgent":
        jobs = jobs.filter(is_urgent=True)
    elif filter_by == "unassigned":
        jobs = jobs.filter(
            tasks__assigned_to__isnull=True,
            tasks__status=ProductionTask.Status.PENDING,
        ).distinct()

    jobs = list(jobs)

    pending_tasks = ProductionTask.objects.filter(
        status=ProductionTask.Status.PENDING
    ).count()
    completed_today = ProductionTask.objects.filter(
        status=ProductionTask.Status.COMPLETED, completed_at__date=today
    ).count()

    stats = {
        "in_production": len(jobs),
        "urgent": sum(1 for j in jobs if j.is_urgent),
        "pending_tasks": pending_tasks,
        "completed_today": completed_today,
    }

    return render(request, "production/admin_overview.html", {
        "jobs": jobs,
        "stats": stats,
        "filter_by": filter_by,
    })


@role_required("ADMIN", "STAFF")
def admin_job_detail(request, pk):
    job = get_object_or_404(
        ProductionJob.objects.select_related("order")
        .prefetch_related(
            "tasks__stage",
            "tasks__assigned_to",
            "tasks__completed_by",
            "tasks__order_item__product",
        ),
        pk=pk,
    )
    operarios = User.objects.filter(
        roles__name="OPERARIO", is_active=True
    ).distinct()
    return render(request, "production/admin_job_detail.html", {
        "job": job,
        "operarios": operarios,
    })


@role_required("ADMIN", "STAFF")
@require_POST
def toggle_urgent(request, pk):
    job = get_object_or_404(ProductionJob, pk=pk)
    ProductionJobService.toggle_urgent(job)
    return redirect("production:admin_overview")


@role_required("ADMIN", "STAFF")
def reglamento(request):
    from production.models import ProductionStage, ProductionRole
    stages = (
        ProductionStage.objects
        .select_related("responsibility__responsible_role")
        .prefetch_related("responsibility__auxiliary_roles")
        .order_by("display_order")
    )
    roles = ProductionRole.objects.prefetch_related(
        "primary_stages",
        "auxiliary_stages",
    ).order_by("name")
    return render(request, "production/reglamento.html", {
        "stages": stages,
        "roles": roles,
    })


@role_required("ADMIN", "STAFF")
@require_POST
def assign_task(request, pk):
    task = get_object_or_404(ProductionTask, pk=pk)
    operario_id = request.POST.get("operario_id")
    if operario_id:
        try:
            operario = User.objects.get(pk=operario_id, roles__name="OPERARIO")
            ProductionJobService.assign_task(task, operario)
            messages.success(request, "Tarea asignada.")
        except User.DoesNotExist:
            messages.error(request, "Operario no encontrado.")
    else:
        ProductionJobService.assign_task(task, None)
        messages.success(request, "Asignación removida.")
    return redirect("production:admin_job_detail", pk=task.job_id)

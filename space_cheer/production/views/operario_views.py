import logging
from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.decorators import role_required
from production.models import (
    OperarioRoleAssignment,
    ProductionJob,
    ProductionStage,
    ProductionTask,
)
from production.services import ProductionJobService

logger = logging.getLogger(__name__)


@role_required("OPERARIO")
def dashboard(request):
    allowed_stages = ProductionStage.objects.filter(
        productionrole__operarioroleassignment__user=request.user
    )
    tasks = (
        ProductionTask.objects.filter(
            status="PENDING",
            stage__in=allowed_stages,
        )
        .filter(Q(assigned_to__isnull=True) | Q(assigned_to=request.user))
        .select_related("job__order", "order_item__product", "stage")
        .order_by("job__is_urgent", "stage__display_order")
    )
    prod_roles = OperarioRoleAssignment.objects.filter(
        user=request.user
    ).select_related("role")
    return render(request, "production/dashboard.html", {
        "tasks": tasks,
        "prod_roles": prod_roles,
    })


@role_required("OPERARIO")
def task_complete(request, pk):
    allowed_stages = ProductionStage.objects.filter(
        productionrole__operarioroleassignment__user=request.user
    )
    task = get_object_or_404(
        ProductionTask,
        pk=pk,
        stage__in=allowed_stages,
        status="PENDING",
    )
    if request.method == "POST":
        started_at_str = request.POST.get("started_at", "")
        notes = request.POST.get("notes", "")[:2000]
        try:
            started_at = timezone.datetime.fromisoformat(started_at_str)
            if timezone.is_naive(started_at):
                started_at = timezone.make_aware(started_at)
            job_created_at_min = task.job.created_at.replace(second=0, microsecond=0)
            if started_at < job_created_at_min:
                messages.error(
                    request,
                    "La fecha de inicio no puede ser anterior a la creación del trabajo.",
                )
                return redirect("production:dashboard")
            ProductionJobService.complete_task(task, request.user, started_at, notes)
            messages.success(request, "Tarea completada.")
        except Exception as exc:
            logger.exception("Error al completar task %s: %s", pk, exc)
            messages.error(request, "Error al completar la tarea.")
    return redirect("production:dashboard")


@role_required("OPERARIO")
def order_design(request, pk):
    job = get_object_or_404(
        ProductionJob,
        pk=pk,
        tasks__assigned_to=request.user,
    )
    design_image = job.order.design_images.filter(is_final=True).first()
    return render(request, "production/order_design.html", {
        "job": job,
        "design_image": design_image,
    })


@role_required("OPERARIO")
def item_measurements(request, pk):
    from orders.models import OrderItem
    allowed_stages = ProductionStage.objects.filter(
        productionrole__operarioroleassignment__user=request.user
    )
    item = get_object_or_404(
        OrderItem,
        pk=pk,
        production_tasks__assigned_to=request.user,
        production_tasks__stage__in=allowed_stages,
    )
    logger.info(
        "PII access: user=%s accessed measurements for OrderItem pk=%s",
        request.user.pk,
        pk,
    )
    athletes = item.athletes.select_related("athlete").prefetch_related(
        "measurements__field"
    ).all()
    return render(request, "production/item_measurements.html", {
        "item": item,
        "athletes": athletes,
    })

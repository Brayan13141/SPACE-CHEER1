import logging
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.decorators import role_required
from accounts.services.pii_audit_service import PiiAuditService
from production.models import (
    OperarioRoleAssignment,
    ProductionJob,
    ProductionStage,
    ProductionTask,
)
from production.services import ProductionJobService

logger = logging.getLogger(__name__)


def _get_allowed_stages(user):
    return ProductionStage.objects.filter(
        productionrole__operarioroleassignment__user=user
    )


def _annotate_blocked_by(tasks):
    """Marca en cada task si una etapa anterior (mismo job+order_item) sigue
    pendiente — la misma condición que ProductionJobService.complete_task
    usa para rechazar el completado (Regla de Oro)."""
    item_ids = {task.order_item_id for task in tasks}
    pending_by_item = {}
    if item_ids:
        for pending_task in (
            ProductionTask.objects.filter(
                order_item_id__in=item_ids,
                status=ProductionTask.Status.PENDING,
            )
            .select_related("stage")
            .order_by("stage__display_order")
        ):
            pending_by_item.setdefault(pending_task.order_item_id, []).append(
                pending_task
            )

    for task in tasks:
        blocker = next(
            (
                pending_task
                for pending_task in pending_by_item.get(task.order_item_id, [])
                if pending_task.stage.display_order < task.stage.display_order
            ),
            None,
        )
        task.blocked_by = blocker.stage.name if blocker else None
    return tasks


@role_required("OPERARIO")
def dashboard(request):
    allowed_stages = _get_allowed_stages(request.user)
    tasks = list(
        ProductionTask.objects.filter(
            status=ProductionTask.Status.PENDING,
            stage__in=allowed_stages,
        )
        .filter(Q(assigned_to__isnull=True) | Q(assigned_to=request.user))
        .select_related("job__order", "order_item__product", "stage")
        .order_by("-job__is_urgent", "stage__display_order")
    )
    _annotate_blocked_by(tasks)
    prod_roles = OperarioRoleAssignment.objects.filter(
        user=request.user
    ).select_related("role")
    return render(request, "production/dashboard.html", {
        "tasks": tasks,
        "prod_roles": prod_roles,
    })


@role_required("OPERARIO")
@require_POST
def task_complete(request, pk):
    allowed_stages = _get_allowed_stages(request.user)
    task = get_object_or_404(
        ProductionTask,
        pk=pk,
        stage__in=allowed_stages,
        status=ProductionTask.Status.PENDING,
    )
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
    except ValidationError as exc:
        messages.error(request, exc.message)
    except Exception as exc:
        logger.exception("Error al completar task %s: %s", pk, exc)
        messages.error(request, "Error al completar la tarea.")
    return redirect("production:dashboard")


@role_required("OPERARIO")
def order_design(request, pk):
    job = get_object_or_404(
        ProductionJob.objects.select_related("order").distinct(),
        pk=pk,
        tasks__assigned_to=request.user,
    )
    design_image = job.order.design_images.filter(is_final=True).first()
    return render(request, "production/order_design.html", {
        "job": job,
        "design_image": design_image,
    })


@role_required("OPERARIO")
def mi_area(request):
    user_roles = list(
        OperarioRoleAssignment.objects
        .filter(user=request.user)
        .select_related("role")
    )
    primary_stages = (
        ProductionStage.objects
        .filter(responsibility__responsible_role__operarioroleassignment__user=request.user)
        .select_related("responsibility__responsible_role")
        .prefetch_related("responsibility__auxiliary_roles")
        .order_by("display_order")
    )
    auxiliary_stages = (
        ProductionStage.objects
        .filter(responsibility__auxiliary_roles__operarioroleassignment__user=request.user)
        .exclude(responsibility__responsible_role__operarioroleassignment__user=request.user)
        .select_related("responsibility__responsible_role")
        .order_by("display_order")
    )
    return render(request, "production/mi_area.html", {
        "user_roles": user_roles,
        "primary_stages": primary_stages,
        "auxiliary_stages": auxiliary_stages,
    })


@role_required("OPERARIO")
def item_measurements(request, pk):
    from orders.models import OrderItem
    allowed_stages = _get_allowed_stages(request.user)
    item = get_object_or_404(
        OrderItem.objects.distinct(),
        pk=pk,
        production_tasks__assigned_to=request.user,
        production_tasks__stage__in=allowed_stages,
    )
    from orders.services.measurements.MeasurementGridService import (
        MeasurementGridService,
    )

    grid = MeasurementGridService.build(item, request.user)

    # Se recorre grid.rows y no item.athletes: asi se audita exactamente a los
    # sujetos que la pagina muestra, sin una consulta extra.
    PiiAuditService.log_many(
        request=request,
        target_users=[row.athlete for row in grid.rows],
        access_type="VIEW_MEASUREMENTS",
        field_accessed="measurements",
        notes=f"OrderItem pk={pk}",
    )

    return render(request, "production/item_measurements.html", {
        "item": item,
        "grid": grid,
    })

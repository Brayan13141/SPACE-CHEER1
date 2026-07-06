import logging
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.decorators import role_required
from production.models import (
    ErrorReport,
    ProductionJob,
    ProductionStage,
)
from production.services import ErrorReportService

logger = logging.getLogger(__name__)
User = get_user_model()

ERROR_TYPES = ErrorReport.ErrorType.choices
ERROR_CAUSES = ErrorReport.ErrorCause.choices
ERROR_IMPACTS = ErrorReport.ErrorImpact.choices


@role_required("OPERARIO", "ADMIN")
def create_error_report(request, job_pk=None):
    stages = ProductionStage.objects.all()
    operarios = User.objects.filter(roles__name="OPERARIO", is_active=True).distinct()
    job = None
    if job_pk:
        job = get_object_or_404(ProductionJob.objects.select_related("order"), pk=job_pk)

    if request.method == "POST":
        description = request.POST.get("description", "").strip()
        if not description:
            messages.error(request, "La descripción del error es obligatoria.")
            return _render_form(request, stages, operarios, job, ERROR_TYPES, ERROR_CAUSES, ERROR_IMPACTS)

        error_types = request.POST.getlist("error_types")
        error_causes = request.POST.getlist("error_causes")
        error_impacts = request.POST.getlist("error_impacts")

        stage_id = request.POST.get("stage") or None
        responsible_id = request.POST.get("responsible") or None

        stage = get_object_or_404(ProductionStage, pk=stage_id) if stage_id else None
        responsible = (
            User.objects.filter(pk=responsible_id).first() if responsible_id else None
        )
        order = job.order if job else None

        try:
            report = ErrorReportService.create(
                reported_by=request.user,
                description=description,
                error_types=error_types,
                order=order,
                job=job,
                stage=stage,
                area=request.POST.get("area", "").strip(),
                error_type_other=request.POST.get("error_type_other", "").strip(),
                responsible=responsible,
                responsible_area=request.POST.get("responsible_area", "").strip(),
                error_causes=error_causes,
                cause_other=request.POST.get("cause_other", "").strip(),
                cause_detail=request.POST.get("cause_detail", "").strip(),
                error_impacts=error_impacts,
                impact_other=request.POST.get("impact_other", "").strip(),
                impact_description=request.POST.get("impact_description", "").strip(),
                corrective_actions=request.POST.get("corrective_actions", "").strip(),
                prevention_actions=request.POST.get("prevention_actions", "").strip(),
            )
            messages.success(
                request,
                f"Reporte #{report.pk} creado correctamente."
                + (" ⚠️ Se detectó necesidad de reposición." if report.requires_reposition else ""),
            )
            if job:
                return redirect("production:admin_job_detail", pk=job.pk)
            return redirect("production:error_report_list")
        except Exception as exc:
            logger.exception("Error al crear ErrorReport: %s", exc)
            messages.error(request, "Ocurrió un error al guardar el reporte.")

    return _render_form(request, stages, operarios, job, ERROR_TYPES, ERROR_CAUSES, ERROR_IMPACTS)


def _render_form(request, stages, operarios, job, error_types, error_causes, error_impacts):
    return render(request, "production/error_report_form.html", {
        "stages": stages,
        "operarios": operarios,
        "job": job,
        "error_types": error_types,
        "error_causes": error_causes,
        "error_impacts": error_impacts,
    })


@role_required("ADMIN")
def error_report_list(request):
    reports = (
        ErrorReport.objects.select_related(
            "reported_by", "responsible", "order", "stage", "job"
        )
        .all()
    )

    status_filter = request.GET.get("status", "")
    if status_filter:
        reports = reports.filter(review_status=status_filter)

    reposition_filter = request.GET.get("reposition", "")
    if reposition_filter == "1":
        reports = reports.filter(requires_reposition=True)

    return render(request, "production/error_report_list.html", {
        "reports": reports,
        "review_statuses": ErrorReport.ReviewStatus.choices,
        "status_filter": status_filter,
        "reposition_filter": reposition_filter,
    })


@role_required("ADMIN")
def error_report_detail(request, pk):
    report = get_object_or_404(
        ErrorReport.objects.select_related(
            "reported_by", "responsible", "reviewed_by",
            "order", "stage", "job__order",
        ),
        pk=pk,
    )
    return render(request, "production/error_report_detail.html", {
        "report": report,
        "review_statuses": ErrorReport.ReviewStatus.choices,
    })


@role_required("ADMIN")
@require_POST
def review_error_report(request, pk):
    report = get_object_or_404(ErrorReport, pk=pk)
    review_status = request.POST.get("review_status", "")
    review_notes = request.POST.get("review_notes", "").strip()
    is_exception = request.POST.get("is_exception") == "1"
    exception_reason = request.POST.get("exception_reason", "").strip()

    valid_statuses = [s for s, _ in ErrorReport.ReviewStatus.choices]
    if review_status not in valid_statuses:
        messages.error(request, "Estado de revisión inválido.")
        return redirect("production:error_report_detail", pk=pk)

    ErrorReportService.review(
        report=report,
        reviewed_by=request.user,
        review_status=review_status,
        review_notes=review_notes,
        is_exception=is_exception,
        exception_reason=exception_reason,
    )
    messages.success(request, f"Reporte #{report.pk} revisado.")
    return redirect("production:error_report_detail", pk=pk)

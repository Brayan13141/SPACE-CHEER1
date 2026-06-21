from django.contrib.auth import get_user_model
from django.shortcuts import render

from accounts.decorators import role_required
from production.models import ProductionRole, ProductionStage, StageResponsibility

User = get_user_model()

# ── Contenido estático de las reglas generales ────────────────────────────────

GENERAL_RULES = [
    {
        "number": 1,
        "icon": "📅",
        "title": "Cumplimiento de Fecha de Entrega",
        "color": "primary",
        "items": [
            "Respetar la fecha comprometida con el cliente.",
            "Informar retrasos antes de que afecten el siguiente proceso.",
            "Entregar su etapa en tiempo y forma.",
            "No retener pedidos innecesariamente.",
        ],
    },
    {
        "number": 2,
        "icon": "✅",
        "title": "Calidad del Producto",
        "color": "success",
        "items": [
            "Entregar únicamente trabajo que cumpla con los estándares de Space Cheer.",
            "No pasar piezas defectuosas al siguiente proceso.",
            "Reportar inmediatamente cualquier defecto detectado.",
            "Corregir errores de su área antes de liberar el trabajo.",
        ],
    },
    {
        "number": 3,
        "icon": "📦",
        "title": "Cuidado de Materiales",
        "color": "warning",
        "items": [
            "Evitar desperdicios innecesarios.",
            "Reportar materiales dañados o faltantes.",
            "Mantener ordenado su proceso de trabajo.",
        ],
    },
    {
        "number": 4,
        "icon": "💬",
        "title": "Comunicación",
        "color": "info",
        "items": [
            "Informar problemas el mismo día que se detecten.",
            "No esperar hasta la fecha de entrega para reportar atrasos.",
            "Mantener actualizada la hoja de seguimiento de producción.",
        ],
    },
]

REPOSITION_ERRORS = [
    "Tallas incorrectas.",
    "Cortes equivocados.",
    "Sublimados incorrectos.",
    "Aplicaciones incorrectas.",
    "Cristalería incorrecta.",
    "Costuras defectuosas.",
    "Pedidos incompletos.",
    "Errores liberados por calidad.",
    "Cualquier error que obligue a rehacer parcial o totalmente el producto.",
]

REPOSITION_EXCEPTIONS = [
    "El error provenga de información incorrecta proporcionada por otra área.",
    "Exista evidencia de que el error fue reportado oportunamente.",
    "El material presente defectos de origen.",
    "La Dirección determine que la causa fue ajena al responsable.",
]


@role_required("ADMIN", "STAFF")
def reglamento(request):
    """Vista completa del reglamento para admin/staff: todas las áreas."""
    roles = (
        ProductionRole.objects.prefetch_related("stages")
        .exclude(error_responsibilities="")
        .order_by("name")
    )
    responsibilities = (
        StageResponsibility.objects.select_related(
            "stage", "responsible_role"
        )
        .prefetch_related("auxiliary_roles")
        .order_by("stage__display_order")
    )
    stages = ProductionStage.objects.all()

    return render(request, "production/reglamento.html", {
        "roles": roles,
        "responsibilities": responsibilities,
        "stages": stages,
        "general_rules": GENERAL_RULES,
        "reposition_errors": REPOSITION_ERRORS,
        "reposition_exceptions": REPOSITION_EXCEPTIONS,
    })


@role_required("OPERARIO", "ADMIN", "STAFF")
def mi_area(request):
    """Vista personalizada para cada operario: solo su área y sus responsabilidades."""
    # Collect all ProductionRoles assigned to this user
    prod_roles = list(
        ProductionRole.objects.filter(
            operarioroleassignment__user=request.user
        )
        .prefetch_related("stages")
        .distinct()
    )

    # For each role, get the stages where this role is primary responsible
    primary_stage_slugs = set()
    for role in prod_roles:
        primary_stage_slugs.update(role.stages.values_list("slug", flat=True))

    # Get StageResponsibility entries relevant to this user's roles
    responsibilities = (
        StageResponsibility.objects.filter(
            responsible_role__in=prod_roles
        )
        .select_related("stage", "responsible_role")
        .prefetch_related("auxiliary_roles")
        .order_by("stage__display_order")
    )

    # Also stages where this user's roles are auxiliaries
    aux_responsibilities = (
        StageResponsibility.objects.filter(
            auxiliary_roles__in=prod_roles
        )
        .exclude(responsible_role__in=prod_roles)
        .select_related("stage", "responsible_role")
        .prefetch_related("auxiliary_roles")
        .order_by("stage__display_order")
        .distinct()
    )

    return render(request, "production/mi_area.html", {
        "prod_roles": prod_roles,
        "responsibilities": responsibilities,
        "aux_responsibilities": aux_responsibilities,
        "general_rules": GENERAL_RULES,
        "reposition_errors": REPOSITION_ERRORS,
        "reposition_exceptions": REPOSITION_EXCEPTIONS,
    })

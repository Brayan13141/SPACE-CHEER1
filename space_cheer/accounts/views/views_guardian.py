# accounts/views_guardian.py
"""
Views para gestión de guardians de atletas menores de edad.

Estas views son llamadas por coaches/admins para:
- Asignar guardian a un atleta menor
- Cambiar el tipo de relación del guardian
- Remover guardian (cuando el atleta llega a mayoría de edad)
- Ver resumen de menores sin guardian

IMPORTANTE: Estas views complementan las de coach/views.py
Se mantienen en accounts porque son dominio de accounts (User, Guardian).
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.exceptions import ValidationError, PermissionDenied
from django.http import HttpResponseNotAllowed
from django.contrib.auth import get_user_model

from accounts.models import UserOwnership
from accounts.services.minor_service import MinorAthleteService
from accounts.services.ownership_service import OwnershipService
from accounts.decorators import role_required
from django.utils import timezone

User = get_user_model()


# =============================================================================
# GUARDIAN MANAGEMENT
# =============================================================================
@role_required("HEADCOACH", "ADMIN")
def headcoach_dashboard(request):
    minors_without_guardian = MinorAthleteService.get_minors_without_guardian(
        request.user
    )

    return render(
        request,
        "account/guardian/headcoach_dashboard.html",
        {
            "minors_without_guardian": minors_without_guardian,
            "count_minors": minors_without_guardian.count(),
        },
    )


@role_required("GUARDIAN", "ADMIN")
def guardian_dashboard(request):
    from accounts.services.minor_service import MinorAthleteService

    athletes = MinorAthleteService.get_athletes_for_guardian(request.user)

    return render(
        request,
        "account/guardian/dashboard.html",
        {"athletes": athletes},
    )


@role_required("HEADCOACH", "ADMIN")
def assign_guardian(request, athlete_id):
    """
    Vista para asignar guardian a un atleta menor.

    Flujo:
    - Solo HEADCOACH / ADMIN
    - Solo atletas menores
    - Solo si el coach tiene ownership del atleta
    """

    athlete = get_object_or_404(User, id=athlete_id)

    # =========================================================
    # 🔐 VALIDACIONES INICIALES
    # =========================================================

    # Validar que sea atleta
    if not athlete.roles.filter(name="ATLETA").exists():
        messages.error(request, "El usuario seleccionado no es un atleta.")
        return redirect("manage_athletes")

    # Validar que sea menor
    if not MinorAthleteService.is_minor(athlete):
        messages.warning(
            request,
            f"{athlete.get_full_name()} no es menor de edad.",
        )
        return redirect("manage_athletes")

    # Validar ownership si es HEADCOACH (no admin)
    if (
        not request.user.is_superuser
        and request.user.roles.filter(name="HEADCOACH").exists()
        and not request.user.roles.filter(name="ADMIN").exists()
    ):
        owns = UserOwnership.objects.filter(
            owner=request.user,
            user=athlete,
            is_active=True,
        ).exists()

        if not owns:
            messages.error(request, "No tienes permiso sobre este atleta.")
            return redirect("manage_athletes")

    # =========================================================
    # 📩 POST → ASIGNAR GUARDIAN
    # =========================================================

    if request.method == "POST":
        guardian_id = request.POST.get("guardian_id")
        relation = request.POST.get("relation", "ACOMP")

        if not guardian_id:
            messages.error(request, "Debes seleccionar un guardian.")
            return redirect("accounts:assign_guardian", athlete_id=athlete.id)

        guardian = get_object_or_404(User, id=guardian_id)

        try:
            # Asignar guardian
            MinorAthleteService.assign_guardian(
                athlete=athlete,
                guardian=guardian,
                assigned_by=request.user,
            )

            # Actualizar relación (opcional)
            if relation in {"PADRE", "TUTOR", "ACOMP"}:
                try:
                    MinorAthleteService.update_guardian_relation(
                        athlete=athlete,
                        relation=relation,
                        updated_by=request.user,
                    )
                except ValidationError:
                    pass

            messages.success(
                request,
                f"Guardian {guardian.get_full_name()} asignado a {athlete.get_full_name()} ✔️",
            )

            return redirect("accounts:minors_without_guardian")

        except (ValidationError, PermissionDenied) as e:
            messages.error(request, str(e))
            return redirect("accounts:assign_guardian", athlete_id=athlete.id)

    # =========================================================
    # 📊 GET → MOSTRAR FORMULARIO
    # =========================================================

    # --- Obtener usuarios del coach ---
    owned_ids = UserOwnership.objects.filter(
        owner=request.user,
        is_active=True,
    ).values_list("user_id", flat=True)

    # --- Base queryset ---
    potential_guardians = User.objects.filter(
        is_active=True,
    ).exclude(id=athlete.id)

    # --- Si es HEADCOACH → limitar a su ecosistema ---
    if not request.user.is_superuser:
        potential_guardians = potential_guardians.filter(id__in=owned_ids)

    # --- Filtrar adultos ---
    today = timezone.now().date()
    eighteen_years_ago = today.replace(year=today.year - 18)

    potential_guardians = potential_guardians.filter(
        birth_date__lte=eighteen_years_ago
    ) | potential_guardians.filter(birth_date__isnull=True)

    # --- Obtener guardian actual ---
    try:
        current_guardian = MinorAthleteService.get_guardian(athlete)
    except ValidationError:
        current_guardian = None

    # --- Menores sin guardian (para UX lateral) ---
    minors_without_guardian = MinorAthleteService.get_minors_without_guardian(
        request.user
    )

    # --- Relaciones ---
    relation_choices = [
        ("PADRE", "Padre / Madre"),
        ("TUTOR", "Tutor legal"),
        ("ACOMP", "Acompañante"),
    ]

    return render(
        request,
        "accounts/guardian/assign_guardian.html",
        {
            "athlete": athlete,
            "potential_guardians": potential_guardians.distinct(),
            "current_guardian": current_guardian,
            "relation_choices": relation_choices,
            "minors_without_guardian": minors_without_guardian,
        },
    )


@role_required("HEADCOACH", "ADMIN")
def remove_guardian(request, athlete_id):
    """
    Remueve el guardian de un atleta (solo si ya es mayor de edad).
    Solo acepta POST para evitar CSRF.
    """
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    athlete = get_object_or_404(User, id=athlete_id)

    try:
        MinorAthleteService.remove_guardian(
            athlete=athlete,
            removed_by=request.user,
        )
        messages.success(
            request,
            f"Guardian removido de {athlete.get_full_name()}.",
        )
    except (ValidationError, PermissionDenied) as e:
        messages.error(request, str(e))

    return redirect("manage_athletes")


@role_required("HEADCOACH", "ADMIN")
def minors_without_guardian_list(request):
    """
    Dashboard: lista de atletas menores SIN guardian asignado.
    Permite al coach identificar menores en situación irregular.
    """
    minors = MinorAthleteService.get_minors_without_guardian(request.user)

    return render(
        request,
        "account/guardian/minors_without_guardian.html",
        {
            "minors": minors,
            "count": minors.count(),
        },
    )


# =============================================================================
# OWNERSHIP MANAGEMENT (complemento de coach/views.py)
# =============================================================================


@role_required("HEADCOACH", "ADMIN")
def ownership_add_user(request, user_id):
    """
    Agrega un usuario al ownership del coach autenticado.
    Útil cuando el admin quiere asignar usuarios directamente.

    POST only — la confirmación viene del template anterior.
    """
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    user_to_add = get_object_or_404(User, id=user_id)

    # El owner es el usuario autenticado (coach)
    # Si es admin, puede especificar un owner diferente
    owner_id = request.POST.get("owner_id")

    if owner_id and (
        request.user.is_superuser or request.user.roles.filter(name="ADMIN").exists()
    ):
        owner = get_object_or_404(User, id=owner_id)
    else:
        owner = request.user

    try:
        OwnershipService.add_to_ownership(
            owner=owner,
            user=user_to_add,
            activated_by=request.user,
        )
        messages.success(
            request,
            f"{user_to_add.get_full_name()} agregado a tu grupo.",
        )
    except (ValidationError, PermissionDenied) as e:
        messages.error(request, str(e))

    return redirect("manage_owned_users")


@role_required("HEADCOACH", "ADMIN")
def ownership_transfer(request, ownership_id):
    """
    Transfiere el ownership de un usuario a otro coach.
    Solo ADMIN puede ejecutar esto.
    """
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    new_owner_id = request.POST.get("new_owner_id")
    if not new_owner_id:
        messages.error(request, "Debes seleccionar el nuevo coach.")
        return redirect("manage_owned_users")

    new_owner = get_object_or_404(User, id=new_owner_id)

    try:
        OwnershipService.transfer_ownership(
            ownership_id=ownership_id,
            new_owner=new_owner,
            transferred_by=request.user,
        )
        messages.success(
            request,
            f"Usuario transferido exitosamente a {new_owner.get_full_name()}.",
        )
    except (ValidationError, PermissionDenied) as e:
        messages.error(request, str(e))

    return redirect("manage_owned_users")

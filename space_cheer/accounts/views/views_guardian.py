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

from asyncio.log import logger

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.exceptions import ValidationError, PermissionDenied
from django.http import HttpResponseNotAllowed
from django.contrib.auth import get_user_model
from django.db.models import Q
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
    """
    Dashboard del guardian.

    Muestra:
    - Atletas bajo su custodia
    - Información de cada atleta (equipo, medidas básicas, estado)
    - Alertas si algún atleta tiene datos incompletos

    Solo ve sus propios atletas asignados.
    """
    from accounts.services.minor_service import MinorAthleteService
    from accounts.models import AthleteProfile

    # Atletas asignados a este guardian
    athletes = MinorAthleteService.get_athletes_for_guardian(request.user)

    # Enriquecer con datos de equipo para el template
    athletes = athletes.prefetch_related(
        "roles",
        "team_memberships__team",
        "athleteprofile",
    )

    # Alertas: atletas sin información completa
    alerts = []
    for athlete in athletes:
        if not athlete.birth_date:
            alerts.append(
                {
                    "athlete": athlete,
                    "message": "Sin fecha de nacimiento registrada.",
                    "level": "warning",
                }
            )
        if not athlete.phone and not athlete.email:
            alerts.append(
                {
                    "athlete": athlete,
                    "message": "Sin datos de contacto.",
                    "level": "info",
                }
            )

    return render(
        request,
        "account/guardian/dashboard.html",
        {
            "athletes": athletes,
            "alerts": alerts,
            "guardian_profile": getattr(request.user, "guardianprofile", None),
        },
    )


@role_required("HEADCOACH", "ADMIN")
def assign_guardian(request, athlete_id):
    """
    Vista para asignar guardian a un atleta menor.

    Dos paths:
    A) Guardian ya registrado → asignar directamente
    B) Guardian no registrado → enviar invitación por email

    El guardian debe haberse registrado con rol GUARDIAN para aparecer
    en la lista. No se crean usuarios guardian desde aquí.
    """
    athlete = get_object_or_404(User, id=athlete_id)

    # --- Validaciones de acceso ---
    if not athlete.roles.filter(name="ATHLETE").exists():
        messages.error(request, "El usuario seleccionado no es un atleta.")
        return redirect("teams:manage_athletes")

    if not MinorAthleteService.is_minor(athlete):
        messages.warning(
            request,
            f"{athlete.get_full_name()} no es menor de edad. "
            "Los guardians solo aplican a menores.",
        )
        return redirect("guardian:minors_without_guardian")

    # HEADCOACH: validar ownership
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
            return redirect("teams:manage_athletes")

    # --- POST: asignar guardian O enviar invitación ---
    if request.method == "POST":
        action = request.POST.get("action")

        # PATH A: Asignar guardian existente
        if action == "assign":
            guardian_id = request.POST.get("guardian_id")
            relation = request.POST.get("relation", "ACOMP")

            if not guardian_id:
                messages.error(request, "Debes seleccionar un guardian.")
                return redirect("guardian:assign_guardian", athlete_id=athlete.id)

            guardian = get_object_or_404(User, id=guardian_id)

            try:
                MinorAthleteService.assign_guardian(
                    athlete=athlete,
                    guardian=guardian,
                    assigned_by=request.user,
                )

                # Actualizar relación si se especificó
                if relation in {"PADRE", "TUTOR", "ACOMP"}:
                    try:
                        MinorAthleteService.update_guardian_relation(
                            athlete=athlete,
                            relation=relation,
                            updated_by=request.user,
                        )
                    except ValidationError:
                        pass  # No crítico si falla esto

                messages.success(
                    request,
                    f"{guardian.get_full_name()} asignado como guardian "
                    f"de {athlete.get_full_name()}.",
                )
                return redirect("guardian:minors_without_guardian")

            except (ValidationError, PermissionDenied) as e:
                messages.error(request, str(e))
                return redirect("guardian:assign_guardian", athlete_id=athlete.id)

        # PATH B: Invitar por email a alguien que aún no está registrado
        elif action == "invite":
            email = request.POST.get("invite_email", "").strip().lower()

            if not email:
                messages.error(request, "Ingresa un email para enviar la invitación.")
                return redirect("guardian:assign_guardian", athlete_id=athlete.id)

            # Verificar si ya existe un usuario con ese email
            if User.objects.filter(email=email).exists():
                existing = User.objects.get(email=email)
                messages.warning(
                    request,
                    f"El email {email} ya está registrado como "
                    f"{existing.get_full_name()}. "
                    "Búscalo en la lista de guardians disponibles.",
                )
                return redirect("guardian:assign_guardian", athlete_id=athlete.id)

            # Enviar invitación usando django-invitations
            try:
                from django.utils import timezone as tz
                from invitations.utils import get_invitation_model

                Invitation = get_invitation_model()

                # Limpiar invitación anterior si existe y está expirada
                existing_inv = Invitation.objects.filter(
                    email=email, accepted=False
                ).first()

                if existing_inv:
                    if existing_inv.key_expired():
                        existing_inv.delete()
                    else:
                        messages.warning(
                            request, f"Ya existe una invitación pendiente para {email}."
                        )
                        return redirect(
                            "guardian:assign_guardian", athlete_id=athlete.id
                        )

                invite = Invitation.create(email=email, inviter=request.user)
                invite.sent = tz.now()
                invite.save()
                invite.send_invitation(request)

                messages.success(
                    request,
                    f"Invitación enviada a {email}. "
                    "Cuando se registre como GUARDIAN, podrás asignarlo aquí.",
                )

            except Exception as e:
                logger.error("Error enviando invitación: %s", str(e), exc_info=True)
                messages.error(request, f"Error enviando invitación: {str(e)}")

            return redirect("guardian:assign_guardian", athlete_id=athlete.id)

    # --- GET: mostrar formulario ---

    # Guardians registrados en el sistema
    # Scope: si es HEADCOACH, solo los de su ownership + los globales sin ownership
    today = timezone.now().date()
    eighteen_years_ago = today.replace(year=today.year - 18)

    # Base: usuarios con rol GUARDIAN, activos, mayores de edad
    guardian_qs = (
        User.objects.filter(
            roles__name="GUARDIAN",
            is_active=True,
        )
        .filter(Q(birth_date__isnull=True) | Q(birth_date__lte=eighteen_years_ago))
        .exclude(id=athlete.id)
        .distinct()
    )

    # Para HEADCOACH: limitar a su ecosistema de owned users
    if (
        not request.user.is_superuser
        and not request.user.roles.filter(name="ADMIN").exists()
    ):
        owned_ids = UserOwnership.objects.filter(
            owner=request.user,
            is_active=True,
        ).values_list("user_id", flat=True)

        guardian_qs = guardian_qs.filter(id__in=owned_ids)

    # Guardian actual del atleta
    try:
        current_guardian = MinorAthleteService.get_guardian(athlete)
    except ValidationError:
        current_guardian = None

    # Menores pendientes (para navegación lateral)
    minors_pending = MinorAthleteService.get_minors_without_guardian(
        request.user
    ).exclude(id=athlete.id)

    return render(
        request,
        "account/guardian/assign_guardian.html",
        {
            "athlete": athlete,
            "potential_guardians": guardian_qs,
            "current_guardian": current_guardian,
            "minors_pending": minors_pending,
            "minors_pending_count": minors_pending.count(),
            "relation_choices": [
                ("PADRE", "Padre / Madre"),
                ("TUTOR", "Tutor legal"),
                ("ACOMP", "Acompañante"),
            ],
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

    return redirect("guardian:minors_without_guardian")


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

    return redirect("coach:manage_owned_users")


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
        return redirect("coach:manage_owned_users")

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

    return redirect("coach:manage_owned_users")

# custody/views.py
"""
Views para gestión de guardians de atletas menores de edad.

Estas views son usadas por coaches/admins para:
- Ver el dashboard de guardians (resumen de menores sin guardian)
- Asignar guardian a un atleta menor
- Remover guardian (cuando el atleta llega a mayoría de edad)
- Ver lista de menores sin guardian
- Dashboard del guardian (vista desde el lado del tutor/padre)

El ownership de coach→usuario vive en accounts y se gestiona desde coach/views.py.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.exceptions import ValidationError, PermissionDenied
from django.http import HttpResponseNotAllowed
from django.db import transaction
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone

from accounts.models import UserOwnership, AthleteProfile
from accounts.services.ownership_service import OwnershipService
from accounts.decorators import role_required
from custody.models import GuardianProfile
from custody.services.minor_service import MinorAthleteService

User = get_user_model()


# =============================================================================
# DASHBOARD DEL HEADCOACH — resumen de menores sin guardian
# =============================================================================


@role_required("HEADCOACH", "ADMIN")
def headcoach_dashboard(request):
    all_minors = MinorAthleteService.get_all_minors(request.user)
    
    minors_with_guardian = []
    minors_without_guardian = []
    
    for minor in all_minors:
        if hasattr(minor, "athleteprofile") and minor.athleteprofile.guardian:
            minors_with_guardian.append(minor)
        else:
            minors_without_guardian.append(minor)

    return render(
        request,
        "account/guardian/headcoach_dashboard.html",
        {
            "minors_with_guardian": minors_with_guardian,
            "minors_without_guardian": minors_without_guardian,
            "count_without": len(minors_without_guardian),
            "count_with": len(minors_with_guardian),
        },
    )


# =============================================================================
# DASHBOARD DEL GUARDIAN
# =============================================================================


@role_required("GUARDIAN", "ADMIN")
def guardian_dashboard(request):
    """
    Dashboard del guardian.

    Muestra:
    - Atletas bajo su custodia
    - Información de cada atleta (equipo, medidas básicas, estado)
    - Alertas si algún atleta tiene datos incompletos
    """
    athletes = MinorAthleteService.get_athletes_for_guardian(request.user)

    athletes = athletes.prefetch_related(
        "roles",
        "team_memberships__team",
        "athleteprofile",
    )

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


# =============================================================================
# GUARDIAN CREA ORDEN PARA SU ATLETA MENOR
# =============================================================================


@role_required("GUARDIAN", "ADMIN")
def guardian_create_order(request, athlete_id):
    """
    El guardian crea una orden PERSONAL en nombre de su atleta menor.
    El guardian es created_by, el menor es owner_user.
    """
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    athlete = get_object_or_404(User, id=athlete_id)

    try:
        if athlete.athleteprofile.guardian != request.user:
            messages.error(request, "No tienes permiso sobre este atleta.")
            return redirect("guardian:dashboard")
    except AthleteProfile.DoesNotExist:
        messages.error(request, "Este usuario no tiene perfil de atleta.")
        return redirect("guardian:dashboard")

    if not athlete.is_minor:
        messages.error(request, "Solo puedes crear pedidos para atletas menores de edad.")
        return redirect("guardian:dashboard")

    from orders.services.state import OrderCreationService
    from orders.services.factories import OrderContactInfoFactory

    try:
        with transaction.atomic():
            order = OrderCreationService.create_order(
                order_type="PERSONAL",
                created_by=request.user,
                owner_user=athlete,
                owner_team=None,
            )
            contact_info = OrderContactInfoFactory.from_user(order=order, user=athlete)
            contact_info.full_clean()
            contact_info.save()
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception("Error creating order for minor athlete_id=%s: %s", athlete_id, e)
        messages.error(request, f"No se pudo crear el pedido: {e}")
        return redirect("guardian:dashboard")

    messages.success(request, f"Pedido creado para {athlete.get_full_name()}.")
    return redirect("orders:contact_info_order", order_id=order.id)


# =============================================================================
# ASIGNAR GUARDIAN
# =============================================================================


@role_required("HEADCOACH", "ADMIN")
def assign_guardian(request, athlete_id):
    """
    Vista para asignar guardian a un atleta menor.

    Dos paths:
    A) Guardian ya registrado → asignar directamente
    B) Guardian no registrado → enviar invitación por email
    """
    import logging
    logger = logging.getLogger(__name__)

    athlete = get_object_or_404(User, id=athlete_id)

    if not athlete.roles.filter(name="ATHLETE").exists():
        messages.error(request, "El usuario seleccionado no es un atleta.")
        return redirect("teams:manage_athletes")

    if not MinorAthleteService.is_minor(athlete):
        messages.warning(
            request,
            f"{athlete.get_full_name()} no es menor de edad. "
            "Los guardians solo aplican a menores.",
        )
        return redirect("guardian:headcoach_dashboard")

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
                    f"{guardian.get_full_name()} asignado como guardian "
                    f"de {athlete.get_full_name()}.",
                )

                # Avisos, no bloqueos: el riesgo no está en la cantidad de
                # atletas sino en que el vínculo sea falso, así que esto se ve
                # y se puede ignorar. Un ValidationError aquí solo enseñaría a
                # elegir "Acompañante" para esquivarlo.
                perfil = GuardianProfile.objects.filter(user=guardian).first()
                if perfil:
                    if perfil.proof_pending:
                        messages.warning(
                            request,
                            f"{guardian.get_full_name()} figura como tutor legal "
                            "y ese vínculo todavía no está verificado. Un "
                            "administrador debe registrar el documento de "
                            "respaldo.",
                        )
                    if perfil.over_soft_limit:
                        messages.warning(
                            request,
                            f"{guardian.get_full_name()} ya tiene "
                            f"{perfil.athlete_count} atletas a su cargo. "
                            "Verifica que sea correcto.",
                        )

                return redirect("guardian:headcoach_dashboard")

            except (ValidationError, PermissionDenied) as e:
                messages.error(request, str(e))
                return redirect("guardian:assign_guardian", athlete_id=athlete.id)

        # PATH B: Invitar por email
        elif action == "invite":
            email = request.POST.get("invite_email", "").strip().lower()

            if not email:
                messages.error(request, "Ingresa un email para enviar la invitación.")
                return redirect("guardian:assign_guardian", athlete_id=athlete.id)

            if User.objects.filter(email=email).exists():
                existing = User.objects.get(email=email)
                messages.warning(
                    request,
                    f"El email {email} ya está registrado como "
                    f"{existing.get_full_name()}. "
                    "Búscalo en la lista de guardians disponibles.",
                )
                return redirect("guardian:assign_guardian", athlete_id=athlete.id)

            try:
                from django.utils import timezone as tz
                from invitations.utils import get_invitation_model

                Invitation = get_invitation_model()

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
                messages.error(request, "Error al enviar la invitación. Contacta al administrador.")

            return redirect("guardian:assign_guardian", athlete_id=athlete.id)

    # GET: mostrar formulario
    today = timezone.now().date()
    eighteen_years_ago = today.replace(year=today.year - 18)

    guardian_qs = (
        User.objects.filter(
            roles__name="GUARDIAN",
            is_active=True,
        )
        .filter(Q(birth_date__isnull=True) | Q(birth_date__lte=eighteen_years_ago))
        .exclude(id=athlete.id)
        .distinct()
    )

    if (
        not request.user.is_superuser
        and not request.user.roles.filter(name="ADMIN").exists()
    ):
        owned_ids = UserOwnership.objects.filter(
            owner=request.user,
            is_active=True,
        ).values_list("user_id", flat=True)

        guardian_qs = guardian_qs.filter(id__in=owned_ids)

    try:
        current_guardian = MinorAthleteService.get_guardian(athlete)
    except ValidationError:
        current_guardian = None

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


# =============================================================================
# REMOVER GUARDIAN
# =============================================================================


@role_required("HEADCOACH", "ADMIN")
def remove_guardian(request, athlete_id):
    """Remueve el guardian de un atleta (solo si ya es mayor de edad)."""
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

    return redirect("guardian:headcoach_dashboard")

# =============================================================================
# OWNERSHIP — complemento de coach/views.py
# =============================================================================


@role_required("HEADCOACH", "ADMIN")
def ownership_add_user(request, user_id):
    """Agrega un usuario al ownership del coach autenticado."""
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    user_to_add = get_object_or_404(User, id=user_id)

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
    """Transfiere el ownership de un usuario a otro coach. Solo ADMIN."""
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


# =============================================================================
# PANTALLA DE BLOQUEO PARA MENORES SIN GUARDIAN
# =============================================================================

from django.contrib.auth.decorators import login_required as _login_required


@_login_required
def minor_blocked(request):
    """Pantalla informativa para menores que aún no tienen guardian asignado."""
    return render(request, "custody/minor_blocked.html")

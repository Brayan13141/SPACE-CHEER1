from django.shortcuts import render, redirect, get_object_or_404
from accounts.decorators import full_profile_required, role_required
from django.utils import timezone
from accounts.models import (
    User,
    Role,
    UserOwnership,
)
from orders.models import OrderItemAthlete
from orders.services.servicesItems.order_item_athlete_service import (
    OrderItemAthleteService,
)
from django.db import transaction
from django.db.models import Prefetch
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseNotAllowed
from teams.models import Team, UserTeamMembership, GLOBAL_ROLE_HIERARCHY
from measures.models import MeasurementField, MeasurementValue
from measures.forms import DynamicMeasurementsForm
import secrets
import string


def can_assume_team_role(user, team_role):
    user_roles = user.roles.values_list("name", flat=True)
    for role in user_roles:
        allowed = GLOBAL_ROLE_HIERARCHY.get(role, [])
        if team_role in allowed:
            return True
    return False


def _generate_temp_password(length=12):
    """Genera contraseña temporal aleatoria."""
    alphabet = string.ascii_letters + string.digits + "!@#$"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _generate_unique_username(base: str) -> str:
    """Genera username único basado en email, sin colisiones."""
    base = base.split("@")[0].lower().replace(".", "_")
    username = base
    counter = 1
    while User.objects.filter(username=username).exists():
        username = f"{base}_{counter}"
        counter += 1
    return username


def _validate_team_access(user, team):
    if user.roles.filter(name="HEADCOACH").exists():
        if team.coach != user:
            raise PermissionDenied


# ─────────────────────────────────────────────────────────────────────────────
# AGREGAR MIEMBRO AL EQUIPO (usuario existente)
# ─────────────────────────────────────────────────────────────────────────────


@full_profile_required
@role_required("ADMIN", "HEADCOACH")
def add_team_member(request, team_id):

    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    team = get_object_or_404(Team, id=team_id, is_active=True)

    if request.user.roles.filter(name="HEADCOACH").exists():
        if team.coach != request.user:
            raise PermissionDenied

    user_id = request.POST.get("user_id")
    role_in_team = request.POST.get("role_in_team", "ATLETA")

    if role_in_team not in dict(UserTeamMembership.ROLE_CHOICES):
        messages.error(request, "Rol de equipo inválido.")
        return redirect("manage_team_members", team_id=team.id)

    if request.user.roles.filter(name="HEADCOACH").exists():
        user = get_object_or_404(
            User,
            id=user_id,
            owner_links__owner=request.user,
            owner_links__is_active=True,
        )
    else:
        user = get_object_or_404(User, id=user_id)

    if not can_assume_team_role(user, role_in_team):
        messages.warning(
            request,
            f"El rol global de {user.get_full_name()} no coincide con '{role_in_team}'. "
            f"Se agregó de todas formas — verifica que sea intencional.",
        )

    membership, _ = UserTeamMembership.objects.get_or_create(user=user, team=team)
    membership.activate(role=role_in_team)

    messages.success(request, f"{user.get_full_name()} agregado al equipo.")
    return redirect("manage_team_members", team_id=team.id)


# ─────────────────────────────────────────────────────────────────────────────
# CREAR CREW MEMBER (usuario nuevo)
# ─────────────────────────────────────────────────────────────────────────────


@full_profile_required
@role_required("HEADCOACH", "ADMIN")
def create_team_crew_member(request, team_id):

    team = get_object_or_404(Team, id=team_id, is_active=True)
    _validate_team_access(request.user, team)

    allowed_global_roles = Role.objects.filter(name__in=["COACH", "STAFF"])

    allowed_team_roles = [
        (value, label)
        for value, label in UserTeamMembership.ROLE_CHOICES
        if value != "ATLETA"
    ]

    # ─────────────────────────────
    # POST
    # ─────────────────────────────
    if request.method == "POST":

        first_name = request.POST.get("first_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()
        email = request.POST.get("email", "").strip().lower()
        global_role_id = request.POST.get("global_role")
        team_role = request.POST.get("team_role")

        # Validación básica
        if not all([first_name, last_name, email, global_role_id, team_role]):
            messages.error(request, "Todos los campos son obligatorios.")
            return redirect("create_team_crew_member", team_id=team.id)

        # Validar rol global
        global_role = get_object_or_404(
            Role,
            id=global_role_id,
            name__in=["COACH", "STAFF"],
        )

        # Validar rol de equipo
        if team_role not in dict(UserTeamMembership.ROLE_CHOICES):
            messages.error(request, "Rol de equipo inválido.")
            return redirect("create_team_crew_member", team_id=team.id)

        try:
            with transaction.atomic():

                # Buscar o crear usuario por email
                user, created = User.objects.get_or_create(
                    email=email,
                    defaults={
                        "username": _generate_unique_username(email),
                        "first_name": first_name,
                        "last_name": last_name,
                        "is_active": True,
                        "profile_completed": False,
                    },
                )

                # ───────────────
                # Usuario NUEVO
                # ───────────────
                if created:
                    temp_password = _generate_temp_password()
                    user.set_password(temp_password)
                    user.save()

                    messages.info(
                        request,
                        f"Usuario nuevo creado para {email}. "
                        f"Se generó una contraseña temporal (envíala por canal seguro).",
                    )

                # ───────────────
                # Usuario EXISTENTE
                # ───────────────
                else:
                    temp_password = None

                    # Detectar conflicto de nombre
                    if user.first_name != first_name or user.last_name != last_name:
                        messages.warning(
                            request,
                            f"El usuario ya existe como "
                            f"{user.get_full_name()} y no se modificó con el nuevo nombre.",
                        )

                # Ownership (relación coach → usuario)
                UserOwnership.objects.get_or_create(
                    owner=request.user,
                    user=user,
                    defaults={"is_active": True},
                )

                # Asignar rol global (sin duplicar)
                if not user.roles.filter(id=global_role.id).exists():
                    user.roles.add(global_role)

                # Membership en equipo
                membership, _ = UserTeamMembership.objects.get_or_create(
                    user=user,
                    team=team,
                )

                membership.activate(role=team_role)

        except Exception as e:
            messages.error(request, f"Error al crear miembro: {str(e)}")
            return redirect("create_team_crew_member", team_id=team.id)

        # Mensaje final
        if created:
            messages.success(
                request,
                f"{user.get_full_name()} fue creado y agregado al equipo correctamente.",
            )
        else:
            messages.success(
                request, f"{user.get_full_name()} fue agregado al equipo correctamente."
            )

        return redirect("manage_team_members", team_id=team.id)

    # ─────────────────────────────
    # GET
    # ─────────────────────────────
    return render(
        request,
        "coach/crew/create_crew_member.html",
        {
            "team": team,
            "global_roles": allowed_global_roles,
            "team_roles": allowed_team_roles,
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# CAMBIAR ROL EN EQUIPO
# ─────────────────────────────────────────────────────────────────────────────


@full_profile_required
@role_required("ADMIN", "HEADCOACH")
def change_team_role(request, membership_id):

    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    membership = get_object_or_404(UserTeamMembership, id=membership_id)

    if request.user.roles.filter(name="HEADCOACH").exists():
        if membership.team.coach != request.user:
            raise PermissionDenied

    new_role = request.POST.get("role_in_team")

    if new_role not in dict(UserTeamMembership.ROLE_CHOICES):
        messages.error(request, "Rol inválido.")
        return redirect("manage_team_members", team_id=membership.team.id)

    if not can_assume_team_role(membership.user, new_role):
        messages.warning(
            request,
            f"El rol global de {membership.user.get_full_name()} no coincide con '{new_role}'. "
            f"Se cambió de todas formas — verifica que sea intencional.",
        )

    membership.activate(role=new_role)
    messages.success(request, "Rol actualizado.")
    return redirect("manage_team_members", team_id=membership.team.id)


# ─────────────────────────────────────────────────────────────────────────────
# RETIRAR MIEMBRO DEL EQUIPO
# ─────────────────────────────────────────────────────────────────────────────


@full_profile_required
@role_required("ADMIN", "HEADCOACH")
def remove_team_member(request, membership_id):

    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    membership = get_object_or_404(UserTeamMembership, id=membership_id)

    if request.user.roles.filter(name="HEADCOACH").exists():
        if membership.team.coach != request.user:
            raise PermissionDenied

    nombre = membership.user.get_full_name()
    membership.deactivate()
    messages.success(request, f"{nombre} retirado del equipo.")
    return redirect("manage_team_members", team_id=membership.team.id)


# ─────────────────────────────────────────────────────────────────────────────
# GESTIONAR USUARIOS PROPIOS (atletas + crew)
# ─────────────────────────────────────────────────────────────────────────────


@full_profile_required
@role_required("HEADCOACH", "ADMIN")
def manage_owned_users(request):

    is_headcoach = request.user.roles.filter(name="HEADCOACH").exists()
    is_admin = request.user.roles.filter(name="ADMIN").exists()

    ownerships = (
        UserOwnership.objects.filter(is_active=True)
        .select_related("user", "owner")
        .prefetch_related(
            Prefetch(
                "user__team_memberships",
                queryset=UserTeamMembership.objects.filter(
                    is_active=True
                ).select_related("team"),
                to_attr="active_memberships",
            )
        )
    )

    if is_headcoach and not is_admin:
        ownerships = ownerships.filter(owner=request.user)

    athletes = ownerships.filter(user__roles__name="ATLETA").distinct()
    crew = ownerships.exclude(user__roles__name="ATLETA").distinct()

    return render(
        request,
        "coach/manage_owned_users.html",
        {
            "athletes": athletes,
            "crew": crew,
            "is_admin": is_admin,
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# LIBERAR USUARIO (quitar del ownership)
# ─────────────────────────────────────────────────────────────────────────────


@full_profile_required
@role_required("HEADCOACH", "ADMIN")
def remove_owned_user(request, ownership_id):

    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    ownership = get_object_or_404(UserOwnership, id=ownership_id, is_active=True)

    if request.user.roles.filter(name="HEADCOACH").exists():
        if ownership.owner != request.user:
            raise PermissionDenied

    nombre = ownership.user.get_full_name()

    # Desactivar ownership
    ownership.is_active = False
    ownership.save(update_fields=["is_active"])

    # Desactivar membresías en equipos del coach
    UserTeamMembership.objects.filter(
        user=ownership.user,
        team__coach=ownership.owner,
        is_active=True,
    ).update(is_active=False, status="inactive", end_date=timezone.now().date())

    messages.success(request, f"{nombre} liberado correctamente.")
    return redirect("manage_owned_users")


# ─────────────────────────────────────────────────────────────────────────────
# EDITAR OWNERSHIP (reasignar coach) — solo ADMIN
# ─────────────────────────────────────────────────────────────────────────────


@full_profile_required
@role_required("HEADCOACH", "ADMIN")
def edit_owned_user(request, ownership_id):

    ownership = get_object_or_404(
        UserOwnership.objects.select_related("user", "owner"),
        id=ownership_id,
        is_active=True,
    )

    if request.user.roles.filter(name="HEADCOACH").exists():
        if ownership.owner != request.user:
            raise PermissionDenied

    if request.method == "POST":
        action = request.POST.get("action")

        if (
            action == "change_owner"
            and request.user.roles.filter(name="ADMIN").exists()
        ):
            new_owner_id = request.POST.get("new_owner")
            new_owner = get_object_or_404(
                User, id=new_owner_id, roles__name="HEADCOACH"
            )
            ownership.owner = new_owner
            ownership.save(update_fields=["owner"])
            messages.success(request, "Coach reasignado correctamente.")
            return redirect("manage_owned_users")

        messages.error(request, "Acción no reconocida.")
        return redirect("manage_owned_users")

    available_coaches = (
        User.objects.filter(roles__name="HEADCOACH", is_active=True)
        if request.user.roles.filter(name="ADMIN").exists()
        else None
    )

    return render(
        request,
        "coach/edit_owned_user.html",
        {
            "ownership": ownership,
            "available_coaches": available_coaches,
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# EDITAR MEDIDAS DE ATLETA
# ─────────────────────────────────────────────────────────────────────────────


@full_profile_required
@role_required("ADMIN", "HEADCOACH")
def edit_athlete_measures(request, id):

    athlete = get_object_or_404(User, id=id)

    if request.user.roles.filter(name="HEADCOACH").exists():
        is_owner = UserOwnership.objects.filter(
            owner=request.user, user=athlete, is_active=True
        ).exists()
        is_in_team = UserTeamMembership.objects.filter(
            user=athlete, team__coach=request.user, is_active=True
        ).exists()

        if not (is_owner or is_in_team):
            messages.error(request, "No tienes acceso a este atleta.")
            return redirect("manage_athletes")

    if request.method == "POST":
        form = DynamicMeasurementsForm(request.POST, user=athlete)

        if form.is_valid():

            #  TRACK CAMBIOS (clave)
            changed = False

            for slug, value in form.cleaned_data.items():
                field = MeasurementField.objects.get(slug=slug)

                existing = MeasurementValue.objects.filter(
                    user=athlete, field=field
                ).first()

                # -------------------------
                # DELETE
                # -------------------------
                if value in ("", None):
                    if existing:
                        existing.delete()
                        changed = True

                # -------------------------
                # CREATE / UPDATE
                # -------------------------
                else:
                    if not existing or existing.value != value:
                        MeasurementValue.objects.update_or_create(
                            user=athlete,
                            field=field,
                            defaults={"value": value},
                        )
                        changed = True

            # -------------------------
            #  SYNC AUTOMÁTICO
            # -------------------------
            if changed:
                athlete_items = OrderItemAthlete.objects.filter(
                    athlete=athlete
                ).prefetch_related("measurements")

                for athlete_item in athlete_items:
                    OrderItemAthleteService.sync_measurements_from_athlete(athlete_item)

            messages.success(request, "Medidas actualizadas.")
            return redirect("edit_athlete_measures", id=id)

    else:
        form = DynamicMeasurementsForm(user=athlete)

    return render(
        request,
        "coach/athlete/edit_measures.html",
        {
            "form": form,
            "athlete": athlete,
        },
    )

from django.shortcuts import render, redirect, get_object_or_404
from accounts.decorators import full_profile_required, role_required
from django.utils import timezone
from accounts.models import (
    User,
    Role,
    AthleteProfile,
    UserOwnership,
    AthleteMedicalInfo,
)
from teams.forms import QuickAthleteRegisterForm
from django.db import transaction
from django.db.models import Prefetch
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseNotAllowed
from teams.models import Team, UserTeamMembership, GLOBAL_ROLE_HIERARCHY
from measures.models import MeasurementField, MeasurementValue
from measures.forms import DynamicMeasurementsForm
from django.db.models import Max
from decouple import config
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

    if request.user.roles.filter(name="HEADCOACH").exists():
        if team.coach != request.user:
            raise PermissionDenied

    allowed_global_roles = Role.objects.filter(name__in=["COACH", "STAFF"])
    allowed_team_roles = [
        (value, label)
        for value, label in UserTeamMembership.ROLE_CHOICES
        if value != "ATLETA"
    ]

    if request.method == "POST":
        first_name = request.POST.get("first_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()
        email = request.POST.get("email", "").strip().lower()
        global_role_id = request.POST.get("global_role")
        team_role = request.POST.get("team_role")

        if not all([first_name, last_name, email, global_role_id, team_role]):
            messages.error(request, "Todos los campos son obligatorios.")
            return redirect("create_team_crew_member", team_id=team.id)

        global_role = get_object_or_404(
            Role, id=global_role_id, name__in=["COACH", "STAFF"]
        )

        if team_role not in dict(UserTeamMembership.ROLE_CHOICES):
            messages.error(request, "Rol de equipo inválido.")
            return redirect("create_team_crew_member", team_id=team.id)

        with transaction.atomic():

            # Buscar por email — si ya existe, reutilizar
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

            # Solo actualizar password si es usuario nuevo
            if created:
                temp_password = _generate_temp_password()
                user.set_password(temp_password)
                user.save()
            else:
                temp_password = None  # ya tiene contraseña, no la pisamos

            UserOwnership.objects.get_or_create(
                owner=request.user,
                user=user,
                defaults={"is_active": True},
            )

            user.roles.add(global_role)

            membership, _ = UserTeamMembership.objects.get_or_create(
                user=user, team=team
            )
            membership.activate(role=team_role)

        if created and temp_password:
            messages.success(
                request,
                f"Crew creado: {user.get_full_name()} ({email}). "
                f"Contraseña temporal: {temp_password} — compártela de forma segura.",
            )
        else:
            messages.success(
                request,
                f"{user.get_full_name()} ya existía en el sistema y fue asignado al equipo.",
            )

        return redirect("manage_team_members", team_id=team.id)

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
            for slug, value in form.cleaned_data.items():
                field = MeasurementField.objects.get(slug=slug)
                if value in ("", None):
                    MeasurementValue.objects.filter(user=athlete, field=field).delete()
                else:
                    MeasurementValue.objects.update_or_create(
                        user=athlete, field=field, defaults={"value": value}
                    )
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

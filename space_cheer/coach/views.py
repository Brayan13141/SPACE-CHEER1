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
from django.db import transaction, models
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseNotAllowed
from teams.models import Team, UserTeamMembership, GLOBAL_ROLE_HIERARCHY
from measures.models import MeasurementField, MeasurementValue
from measures.forms import DynamicMeasurementsForm
from django.db.models import Max


def can_assume_team_role(user, team_role):
    user_roles = user.roles.values_list("name", flat=True)

    for role in user_roles:
        allowed = GLOBAL_ROLE_HIERARCHY.get(role, [])
        if team_role in allowed:
            return True

    return False


# Vista para agregar miembro al equipo
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
        messages.error(request, "Rol de equipo inválido")
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

    # Soft validation: solo advertencia
    if not can_assume_team_role(user, role_in_team):
        messages.warning(
            request,
            "Advertencia: el rol global del usuario no coincide con su rol en el equipo. "
            "Esto es permitido, pero revisa que sea intencional.",
        )

    membership, _ = UserTeamMembership.objects.get_or_create(
        user=user,
        team=team,
    )

    membership.activate(role=role_in_team)

    messages.success(request, "Miembro agregado al equipo")
    return redirect("manage_team_members", team_id=team.id)


# Vista para cambiar rol de miembro del equipo
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
        messages.error(request, "Rol inválido")
        return redirect("manage_team_members", team_id=membership.team.id)

    if not can_assume_team_role(membership.user, new_role):
        messages.warning(
            request,
            "Advertencia: el rol global del usuario no coincide con su nuevo rol en el equipo.",
            "Esto es permitido, pero revisa que sea intencional.",
        )

    membership.activate(role=new_role)

    messages.success(request, "Rol del miembro actualizado")
    return redirect("manage_team_members", team_id=membership.team.id)


# Vista para cambiar rol de miembro del equipo
@role_required("ADMIN", "HEADCOACH")
def remove_team_member(request, membership_id):
    # 1 solo post
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    # 2 obtener membresia
    membership = get_object_or_404(UserTeamMembership, id=membership_id)

    # 3 seguridad
    if request.user.roles.filter(name="HEADCOACH").exists():
        if membership.team.coach != request.user:
            raise PermissionDenied

    # 4 desactivar membresia sin borrar historico
    membership.deactivate()

    messages.success(request, "Miembro retirado")
    return redirect("manage_team_members", team_id=membership.team.id)


# Vista para editar medidas de atleta
@full_profile_required
@role_required("ADMIN", "HEADCOACH")
def edit_athlete_measures(request, id):
    # 1 obtener atleta
    athlete = get_object_or_404(User, id=id)

    # 2 seguridad para headcoach
    if request.user.roles.filter(name="HEADCOACH").exists():
        is_owner = UserOwnership.objects.filter(
            owner=request.user,
            user=athlete,
            is_active=True,
        ).exists()

        is_in_team = UserTeamMembership.objects.filter(
            user=athlete,
            team__coach=request.user,
            is_active=True,
        ).exists()

        if not (is_owner or is_in_team):
            messages.error(request, "Acceso denegado")
            return redirect("manage_athletes")

    # 3 manejo del formulario dinamico
    if request.method == "POST":
        form = DynamicMeasurementsForm(request.POST, user=athlete)

        if form.is_valid():
            for slug, value in form.cleaned_data.items():
                field = MeasurementField.objects.get(slug=slug)

                if value in ("", None):
                    MeasurementValue.objects.filter(
                        user=athlete,
                        field=field,
                    ).delete()
                else:
                    MeasurementValue.objects.update_or_create(
                        user=athlete,
                        field=field,
                        defaults={"value": value},
                    )

            messages.success(request, "Medidas actualizadas")
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


# Vista para crear miembro del equipo
@full_profile_required
@role_required("ADMIN", "HEADCOACH")
def create_team_crew_member(request, team_id):

    team = get_object_or_404(Team, id=team_id, is_active=True)

    if request.user.roles.filter(name="HEADCOACH").exists():
        if team.coach != request.user:
            raise PermissionDenied

    allowed_global_roles = Role.objects.filter(
        name__in=["COACH", "STAFF", "ACOMPAÑANTE"]
    )

    allowed_team_roles = [role for role in UserTeamMembership.ROLE_CHOICES]

    if request.method == "POST":

        first_name = request.POST.get("first_name")
        last_name = request.POST.get("last_name")
        email = request.POST.get("email")
        global_role_id = request.POST.get("global_role")
        team_role = request.POST.get("team_role")

        if not all([first_name, last_name, email, global_role_id, team_role]):
            messages.error(request, "Todos los campos son obligatorios")
            return redirect("create_team_crew_member", team_id=team.id)

        global_role = get_object_or_404(Role, id=global_role_id)

        if team_role not in dict(UserTeamMembership.ROLE_CHOICES):
            messages.error(request, "Rol de equipo inválido")
            return redirect("create_team_crew_member", team_id=team.id)

        with transaction.atomic():

            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    "username": email,
                    "first_name": first_name,
                    "last_name": last_name,
                    "is_active": True,
                    "profile_completed": False,
                },
            )
            user.set_password("$Temporal123")
            user.save()

            UserOwnership.objects.get_or_create(
                owner=request.user,
                user=user,
                defaults={"is_active": True},
            )

            user.roles.add(global_role)

            membership, _ = UserTeamMembership.objects.get_or_create(
                user=user,
                team=team,
            )

            membership.activate(role=team_role)

        messages.success(
            request,
            "Miembro del crew creado y asignado. "
            "El usuario deberá completar su perfil al iniciar sesión.",
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


@full_profile_required
@role_required("HEADCOACH", "ADMIN")
def manage_owned_users(request):

    # ---------------- RESOLVER CONTEXTO ----------------
    is_headcoach = request.user.roles.filter(name="HEADCOACH").exists()
    is_admin = request.user.roles.filter(name="ADMIN").exists()

    # ---------------- OWNERSHIPS ACTIVOS ----------------
    ownerships = UserOwnership.objects.filter(is_active=True).select_related(
        "user", "owner"
    )

    # HEADCOACH solo ve los suyos
    if is_headcoach and not is_admin:
        ownerships = ownerships.filter(owner=request.user)

    # ---------------- CLASIFICACIÓN ----------------
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


@full_profile_required
@role_required("HEADCOACH", "ADMIN")
def remove_owned_user(request, ownership_id):

    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    ownership = get_object_or_404(UserOwnership, id=ownership_id, is_active=True)

    # Seguridad HEADCOACH
    if request.user.roles.filter(name="HEADCOACH").exists():
        if ownership.owner != request.user:
            raise PermissionDenied

    # 1. Desactivar ownership
    ownership.is_active = False
    ownership.save()

    # 2. Opcional: desactivar membresías activas en equipos de ese coach
    UserTeamMembership.objects.filter(
        user=ownership.user, team__coach=ownership.owner, is_active=True
    ).update(is_active=False, status="inactive", end_date=timezone.now().date())

    messages.success(request, "Usuario liberado del HeadCoach")
    return redirect("manage_owned_users")


@full_profile_required
@role_required("HEADCOACH", "ADMIN")
def edit_owned_user(request, ownership_id):

    ownership = get_object_or_404(
        UserOwnership.objects.select_related("user", "owner"),
        id=ownership_id,
        is_active=True,
    )

    # ---------------- SEGURIDAD ----------------
    if request.user.roles.filter(name="HEADCOACH").exists():
        if ownership.owner != request.user:
            raise PermissionDenied

    # ---------------- PROCESAR POST ----------------
    if request.method == "POST":
        action = request.POST.get("action")

        if action == "deactivate":
            ownership.is_active = False
            ownership.owner = None
            ownership.save()

            messages.success(request, "Usuario liberado correctamente")
            return redirect("manage_owned_users")

        if (
            action == "change_owner"
            and request.user.roles.filter(name="ADMIN").exists()
        ):
            new_owner_id = request.POST.get("new_owner")

            new_owner = get_object_or_404(
                User,
                id=new_owner_id,
                roles__name="HEADCOACH",
            )

            ownership.owner = new_owner
            ownership.save()

            messages.success(request, "Coach reasignado correctamente")
            return redirect("manage_owned_users")

    # ---------------- DATOS PARA TEMPLATE ----------------
    available_coaches = (
        User.objects.filter(
            roles__name="HEADCOACH",
            is_active=True,
        )
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

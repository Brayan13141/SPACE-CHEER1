import logging

from decouple import config

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.exceptions import PermissionDenied

logger = logging.getLogger(__name__)

from accounts.models import User
from accounts.decorators import role_required
from accounts.services import AthleteService
from accounts.services.permission_service import AccountPermissions

from .models import Team, TeamCategory, UserTeamMembership
from .forms import TeamForm, TeamCategoryForm, QuickAthleteRegisterForm
from .services import TeamService, MembershipService


@role_required("ADMIN", "HEADCOACH")
def manage_categories(request):
    categorias = TeamCategory.objects.all()
    puede_gestionar = AccountPermissions.can_manage_teams(request.user)

    form_crear = TeamCategoryForm()
    form_editar = None
    abrir_modal_crear = False
    abrir_modal_editar = False
    categoria_editar_id = None

    if request.method == "POST":

        if "crear_categoria" in request.POST and puede_gestionar:
            form_crear = TeamCategoryForm(request.POST)
            if form_crear.is_valid():
                form_crear.save()
                messages.success(
                    request,
                    f"Categoría '{form_crear.cleaned_data['name']}' creada exitosamente.",
                )
                return redirect("teams:manage_categories")
            abrir_modal_crear = True

        elif "editar_categoria" in request.POST and puede_gestionar:
            categoria_id = request.POST.get("categoria_id")
            categoria = get_object_or_404(TeamCategory, id=categoria_id)
            form_editar = TeamCategoryForm(request.POST, instance=categoria)
            if form_editar.is_valid():
                form_editar.save()
                messages.success(
                    request,
                    f"Categoría '{form_editar.cleaned_data['name']}' actualizada exitosamente.",
                )
                return redirect("teams:manage_categories")
            abrir_modal_editar = True
            categoria_editar_id = categoria_id

        elif "eliminar_categoria" in request.POST and puede_gestionar:
            categoria_id = request.POST.get("categoria_id")
            if categoria_id:
                categoria = get_object_or_404(TeamCategory, id=categoria_id)
                nombre = categoria.name
                categoria.delete()
                messages.success(request, f"Categoría '{nombre}' eliminada exitosamente.")
            return redirect("teams:manage_categories")

    return render(
        request,
        "teams/manage_categories.html",
        {
            "categorias": categorias,
            "form_crear": form_crear,
            "form_editar": form_editar,
            "abrir_modal_crear": abrir_modal_crear,
            "abrir_modal_editar": abrir_modal_editar,
            "categoria_editar_id": categoria_editar_id,
            "puede_crear": puede_gestionar,
            "puede_editar": puede_gestionar,
            "puede_eliminar": puede_gestionar,
        },
    )


@role_required("ADMIN", "HEADCOACH")
def manage_teams(request):
    if request.user.roles.filter(name="HEADCOACH").exists():
        teams = Team.objects.select_related("coach", "category").filter(
            coach=request.user
        )
    else:
        teams = Team.objects.select_related("coach", "category").all()

    puede_gestionar = AccountPermissions.can_manage_teams(request.user)

    form_crear = TeamForm(request=request)
    form_editar = None
    abrir_modal_crear = False
    abrir_modal_editar = False
    team_editar_id = None

    if request.method == "POST":

        if "crear_team" in request.POST and puede_gestionar:
            form_crear = TeamForm(request.POST, request.FILES, request=request)
            if form_crear.is_valid():
                team = TeamService.create_team(form=form_crear)
                messages.success(request, f"Equipo '{team.name}' creado exitosamente.")
                return redirect("teams:manage_teams")
            for field, errors in form_crear.errors.items():
                for error in errors:
                    label = "" if field == "__all__" else f"{field}: "
                    messages.error(request, f"{label}{error}")
            abrir_modal_crear = True

        elif "editar_team" in request.POST and puede_gestionar:
            team_id = request.POST.get("team_id")
            team = get_object_or_404(Team, id=team_id)
            form_editar = TeamForm(request.POST, request.FILES, instance=team, request=request)
            if form_editar.is_valid():
                form_editar.save()
                messages.success(
                    request,
                    f"Equipo '{form_editar.cleaned_data['name']}' actualizado exitosamente.",
                )
                return redirect("teams:manage_teams")
            for field, errors in form_editar.errors.items():
                for error in errors:
                    label = "" if field == "__all__" else f"{field}: "
                    messages.error(request, f"{label}{error}")
            abrir_modal_editar = True
            team_editar_id = team_id

        elif "eliminar_team" in request.POST and puede_gestionar:
            team_id = request.POST.get("team_id")
            team = get_object_or_404(Team, id=team_id)
            success, msg = TeamService.delete_team(team=team)
            if success:
                messages.success(request, msg)
            else:
                messages.error(request, msg)
            return redirect("teams:manage_teams")

    return render(
        request,
        "teams/manage_teams.html",
        {
            "teams": teams,
            "form_crear": form_crear,
            "form_editar": form_editar,
            "abrir_modal_crear": abrir_modal_crear,
            "abrir_modal_editar": abrir_modal_editar,
            "team_editar_id": team_editar_id,
            "puede_crear": puede_gestionar,
            "puede_editar": puede_gestionar,
            "puede_eliminar": puede_gestionar,
        },
    )


@role_required("ADMIN", "HEADCOACH")
def manage_team_members(request, team_id):
    team = get_object_or_404(Team, id=team_id, is_active=True)

    if request.user.roles.filter(name="HEADCOACH").exists():
        if team.coach != request.user:
            raise PermissionDenied

    is_admin = request.user.roles.filter(name="ADMIN").exists()
    is_headcoach = request.user.roles.filter(name="HEADCOACH").exists()

    memberships = (
        UserTeamMembership.objects.filter(team=team)
        .select_related("user")
        .order_by("role_in_team", "user__first_name")
    )

    active_members = memberships.filter(is_active=True, status="accepted")
    pending_members = memberships.filter(status="pending")
    inactive_members = memberships.filter(is_active=False)

    available_users = MembershipService.get_available_users(
        team=team,
        requesting_user=request.user,
    )

    return render(
        request,
        "teams/add_members.html",
        {
            "team": team,
            "active_members": active_members,
            "pending_members": pending_members,
            "inactive_members": inactive_members,
            "available_users": available_users,
            "role_choices": UserTeamMembership.ROLE_CHOICES,
            "is_admin": is_admin,
            "is_headcoach": is_headcoach,
        },
    )


@role_required("ADMIN", "HEADCOACH")
def manage_athletes(request):
    puede_crear = AccountPermissions.can_manage_teams(request.user)

    if request.user.roles.filter(name="HEADCOACH").exists():
        athletes = User.objects.filter(
            roles__name="ATHLETE",
            owner_links__owner=request.user,
            owner_links__is_active=True,
        ).distinct()
    else:
        athletes = User.objects.filter(roles__name="ATHLETE").distinct()

    form_crear = QuickAthleteRegisterForm()
    abrir_modal_crear = False

    if request.method == "POST":
        if "crear_alumno" in request.POST and puede_crear:
            form_crear = QuickAthleteRegisterForm(request.POST)
            if form_crear.is_valid():
                cd = form_crear.cleaned_data
                try:
                    user = AthleteService.create_quick(
                        first_name=cd["first_name"],
                        last_name=cd["last_name"],
                        email=cd.get("email", ""),
                        phone=cd.get("phone", ""),
                        created_by=request.user,
                    )
                    messages.success(
                        request,
                        f"Alumno creado. Usuario: {user.username}. "
                        "La contraseña temporal fue enviada al correo",
                    )
                    return redirect("teams:manage_athletes")
                except Exception as e:
                    # No exponer detalles internos al usuario — solo loggear
                    logger.exception("Error al crear atleta rápido por user=%s: %s", request.user.id, e)
                    messages.error(request, "Error al crear el atleta. Contacta al administrador.")

            abrir_modal_crear = True

    return render(
        request,
        "coach/athlete/manage_athletes.html",
        {
            "athletes": athletes,
            "form_crear": form_crear,
            "abrir_modal_crear": abrir_modal_crear,
            "puede_crear": puede_crear,
        },
    )

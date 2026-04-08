# views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import Team, TeamCategory
from .forms import TeamForm, TeamCategoryForm, QuickAthleteRegisterForm
from accounts.decorators import role_required
from accounts.models import (
    User,
    Role,
    AthleteProfile,
    AthleteMedicalInfo,
    UserOwnership,
)

from django.db import models
from teams.models import UserTeamMembership
from django.utils import timezone
from django.db import transaction
from django.db.models import Max
from django.core.exceptions import PermissionDenied
from decouple import config
from django.db.models import ProtectedError


@role_required("ADMIN", "HEADCOACH")
def manage_categories(request):

    categorias = TeamCategory.objects.all()

    # Permisos por rol
    puede_crear = request.user.roles.filter(name__in=["ADMIN", "HEADCOACH"]).exists()
    puede_editar = request.user.roles.filter(name__in=["ADMIN", "HEADCOACH"]).exists()
    puede_eliminar = request.user.roles.filter(name__in=["ADMIN", "HEADCOACH"]).exists()

    # Formularios
    form_crear = TeamCategoryForm()
    form_editar = None

    # Control modal
    abrir_modal_crear = False
    abrir_modal_editar = False
    categoria_editar_id = None

    if request.method == "POST":

        # CREAR
        if "crear_categoria" in request.POST and puede_crear:
            form_crear = TeamCategoryForm(request.POST)
            if form_crear.is_valid():
                form_crear.save()
                messages.success(
                    request,
                    f"Categoría '{form_crear.cleaned_data['name']}' creada exitosamente.",
                )
                return redirect("manage_categories")
            abrir_modal_crear = True

        # EDITAR
        elif "editar_categoria" in request.POST and puede_editar:
            categoria_id = request.POST.get("categoria_id")
            categoria = get_object_or_404(TeamCategory, id=categoria_id)

            form_editar = TeamCategoryForm(request.POST, instance=categoria)

            if form_editar.is_valid():
                form_editar.save()
                messages.success(
                    request,
                    f"Categoría '{form_editar.cleaned_data['name']}' actualizada exitosamente.",
                )
                return redirect("manage_categories")

            # Error → volvemos a mostrar el modal
            abrir_modal_editar = True
            categoria_editar_id = categoria_id

        # ELIMINAR
        elif "eliminar_categoria" in request.POST and puede_eliminar:
            categoria_id = request.POST.get("categoria_id")
            if categoria_id:
                categoria = get_object_or_404(TeamCategory, id=categoria_id)
                nombre_eliminado = categoria.name
                categoria.delete()
                messages.success(
                    request, f"Categoría '{nombre_eliminado}' eliminada exitosamente."
                )
            return redirect("manage_categories")

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
            "puede_crear": puede_crear,
            "puede_editar": puede_editar,
            "puede_eliminar": puede_eliminar,
        },
    )


@role_required("ADMIN", "HEADCOACH")
def manage_teams(request):

    if request.user.roles.filter(name__in=["HEADCOACH"]).exists():
        teams = Team.objects.select_related("coach", "category").filter(
            coach=request.user
        )
    else:
        teams = Team.objects.select_related("coach", "category").all()

    # Permisos
    puede_crear = (
        request.user.is_superuser
        or request.user.roles.filter(name__in=["ADMIN", "HEADCOACH"]).exists()
    )
    puede_editar = (
        request.user.is_superuser
        or request.user.roles.filter(name__in=["ADMIN", "HEADCOACH"]).exists()
    )
    puede_eliminar = (
        request.user.is_superuser
        or request.user.roles.filter(name__in=["ADMIN", "HEADCOACH"]).exists()
    )

    # Formularios
    form_crear = TeamForm(request=request)
    form_editar = None

    # Control de modales
    abrir_modal_crear = False
    abrir_modal_editar = False
    team_editar_id = None

    # ---------------- POST ----------------
    if request.method == "POST":

        # CREAR
        if "crear_team" in request.POST and puede_crear:
            form_crear = TeamForm(request.POST, request.FILES)
            if form_crear.is_valid():
                team = form_crear.save()
                UserTeamMembership.objects.create(
                    user=team.coach,
                    team=team,
                    role_in_team="HEADCOACH",
                    status="accepted",
                    is_active=True,
                )
                messages.success(request, f"Equipo '{team.name}' creado exitosamente.")
                return redirect("manage_teams")
            abrir_modal_crear = True

        # EDITAR
        elif "editar_team" in request.POST and puede_editar:
            team_id = request.POST.get("team_id")
            team = get_object_or_404(Team, id=team_id)

            form_editar = TeamForm(request.POST, request.FILES, instance=team)

            if form_editar.is_valid():
                form_editar.save()
                messages.success(
                    request,
                    f"Equipo '{form_editar.cleaned_data['name']}' actualizado exitosamente.",
                )
                return redirect("manage_teams")

            # Volver a abrir modal con errores
            abrir_modal_editar = True
            team_editar_id = team_id

        # ELIMINAR
        elif "eliminar_team" in request.POST and puede_eliminar:
            team_id = request.POST.get("team_id")
            team = get_object_or_404(Team, id=team_id)
            nombre = team.name

            try:
                team.delete()
                messages.success(request, f"Equipo '{nombre}' eliminado exitosamente.")

            except ProtectedError as e:
                # Separar órdenes de productos en el mensaje
                orders = [
                    o for o in e.protected_objects if o.__class__.__name__ == "Order"
                ]
                products = [
                    p for p in e.protected_objects if p.__class__.__name__ == "Product"
                ]

                partes = []
                if orders:
                    partes.append(f"{len(orders)} orden(es)")
                if products:
                    partes.append(f"{len(products)} producto(s) exclusivo(s)")

                messages.error(
                    request,
                    f"No se puede eliminar el equipo '{nombre}' porque tiene "
                    f"{' y '.join(partes)} asociados. "
                    f"Cancela o reasigna esos registros antes de eliminarlo.",
                )

            return redirect("manage_teams")

    # ---------------- RENDER ----------------
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
            "puede_crear": puede_crear,
            "puede_editar": puede_editar,
            "puede_eliminar": puede_eliminar,
        },
    )


# Vistas para Agregar o eliminar miembros del equipo y atletas


@role_required("ADMIN", "HEADCOACH")
def manage_team_members(request, team_id):

    team = get_object_or_404(Team, id=team_id, is_active=True)

    # Seguridad: HEADCOACH solo puede ver su propio equipo
    if request.user.roles.filter(name="HEADCOACH").exists():
        if team.coach != request.user:
            raise PermissionDenied

    is_admin = request.user.roles.filter(name="ADMIN").exists()
    is_headcoach = request.user.roles.filter(name="HEADCOACH").exists()

    # ── Miembros del equipo ───────────────────────────────────────────────
    memberships = (
        UserTeamMembership.objects.filter(team=team)
        .select_related("user")
        .order_by("role_in_team", "user__first_name")
    )

    active_members = memberships.filter(is_active=True, status="accepted")
    pending_members = memberships.filter(status="pending")
    inactive_members = memberships.filter(is_active=False)

    # ── Candidatos a agregar (excluye solo membresías ACTIVAS) ────────────
    already_active_ids = active_members.values_list("user_id", flat=True)

    if is_admin:
        # ADMIN ve a todos los usuarios del sistema excepto los ya activos
        available_users = (
            User.objects.exclude(id__in=already_active_ids)
            .exclude(id=team.coach_id)  # el coach ya es dueño del equipo
            .order_by("first_name")
            .distinct()
        )
    else:
        # HEADCOACH solo ve sus owned users (atletas + crew)
        available_users = (
            User.objects.filter(
                owner_links__owner=request.user,
                owner_links__is_active=True,
            )
            .exclude(id__in=already_active_ids)
            .order_by("first_name")
            .distinct()
        )

    # Roles disponibles para asignar en el equipo
    role_choices = UserTeamMembership.ROLE_CHOICES

    return render(
        request,
        "teams/add_members.html",
        {
            "team": team,
            "active_members": active_members,
            "pending_members": pending_members,
            "inactive_members": inactive_members,
            "available_users": available_users,
            "role_choices": role_choices,  # ← nombre consistente con el template
            "is_admin": is_admin,
            "is_headcoach": is_headcoach,
        },
    )


# Vista para CRUD SOLO ATLETAS


@role_required("ADMIN", "HEADCOACH")
def manage_athletes(request):
    # 1 verificar si el usuario tiene permiso para crear atletas
    puede_crear = request.user.roles.filter(name__in=["ADMIN", "HEADCOACH"]).exists()

    # 2 listado de atletas
    # headcoach solo ve atletas que posee
    if request.user.roles.filter(name="HEADCOACH").exists():
        athletes = User.objects.filter(
            roles__name="ATLETA",
            owner_links__owner=request.user,
            owner_links__is_active=True,
        ).distinct()
    else:
        athletes = User.objects.filter(roles__name="ATLETA").distinct()

    # 3 formulario de creacion rapida
    form_crear = QuickAthleteRegisterForm()
    abrir_modal_crear = False

    # 4 manejo de peticiones post
    if request.method == "POST":
        if "crear_alumno" in request.POST and puede_crear:
            form_crear = QuickAthleteRegisterForm(request.POST)

            if form_crear.is_valid():
                cd = form_crear.cleaned_data

                # 5 transaccion atomica para evitar datos inconsistentes
                with transaction.atomic():
                    # 6 generar username incremental seguro
                    max_num = (
                        User.objects.filter(username__startswith="ATHLETE-")
                        .annotate(
                            num=models.functions.Cast(
                                models.functions.Substr("username", 9),
                                models.IntegerField(),
                            )
                        )
                        .aggregate(max_num=Max("num"))["max_num"]
                    ) or 0

                    username = f"ATHLETE-{max_num + 1}"

                    # 7 crear usuario base
                    user = User.objects.create_user(
                        username=username,
                        first_name=cd["first_name"],
                        last_name=cd["last_name"],
                        email=cd.get("email", ""),
                        phone=cd.get("phone", ""),
                        password=config(
                            "ATHLETE_TEMP_PASSWORD", default="$Temporal123"
                        ),
                        profile_completed=False,
                    )

                    # 8 asignar rol global atleta
                    user.roles.add(Role.objects.get(name="ATLETA"))

                    # 9 crear perfil atleta
                    athlete_profile, _ = AthleteProfile.objects.get_or_create(
                        user=user,
                        defaults={
                            "emergency_contact": "POR DEFINIR",
                            "emergency_phone": "",
                        },
                    )

                    # 10 crear informacion medica basica
                    AthleteMedicalInfo.objects.get_or_create(athlete=athlete_profile)

                    # 11 asignar propiedad del atleta al coach creador
                    UserOwnership.objects.create(
                        owner=request.user,
                        user=user,
                    )

                messages.success(
                    request,
                    f"Alumno creado usuario {username} password temporal {config('ATHLETE_TEMP_PASSWORD', default='$Temporal123')}",
                )
                return redirect("manage_athletes")

            # 12 si hay error se reabre el modal
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

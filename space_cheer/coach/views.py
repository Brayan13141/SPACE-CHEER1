# coach/views.py
"""
Views para coaches (HEADCOACH/ADMIN).

Gestiona:
- Atletas: crear, editar medidas, ver menores sin guardian
- Owned users: listar, remover, reasignar a otro coach
- Team members: agregar, cambiar rol, retirar
- Crew: crear staff/coaches

Todos los servicios de dominio viven en:
- accounts/services/ownership_service.py → OwnershipService
- accounts/services/minor_service.py     → MinorAthleteService

Las views solo orquestan: obtener datos → llamar servicio → mensaje → redirect.
"""

import logging
import secrets
import string
from datetime import date

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from decouple import config

from accounts.decorators import role_required
from accounts.models import (
    AthleteMedicalInfo,
    AthleteProfile,
    Role,
    UserOwnership,
)
from accounts.services.minor_service import MinorAthleteService
from accounts.services.ownership_service import OwnershipService
from measures.forms import DynamicMeasurementsForm
from measures.models import MeasurementField, MeasurementValue
from teams.forms import QuickAthleteRegisterForm
from teams.models import Team, UserTeamMembership, GLOBAL_ROLE_HIERARCHY

logger = logging.getLogger(__name__)
User = get_user_model()


# =============================================================================
# HELPERS LOCALES
# =============================================================================


def _can_assume_team_role(user, team_role) -> bool:
    """Verifica si el rol global del usuario es compatible con el rol de equipo."""
    user_roles = user.roles.values_list("name", flat=True)
    for role in user_roles:
        allowed = GLOBAL_ROLE_HIERARCHY.get(role, [])
        if team_role in allowed:
            return True
    return False


def _generate_temp_password(length=12) -> str:
    """Genera contraseña temporal aleatoria segura."""
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
    """Verifica que un HEADCOACH es el coach del equipo."""
    if user.roles.filter(name="HEADCOACH").exists():
        if team.coach != user:
            raise PermissionDenied("No tienes acceso a este equipo.")


# =============================================================================
# GESTIONAR USUARIOS PROPIOS (atletas + crew)
# =============================================================================


@role_required("HEADCOACH", "ADMIN")
def manage_owned_users(request):
    """
    Lista todos los usuarios owned por el coach autenticado.
    ADMIN ve todos; HEADCOACH solo ve los suyos.
    Incluye alerta si hay menores sin guardian.
    """
    from django.db.models import Prefetch

    is_headcoach = request.user.roles.filter(name="HEADCOACH").exists()
    is_admin = (
        request.user.is_superuser or request.user.roles.filter(name="ADMIN").exists()
    )

    # --- Obtener ownerships según rol ---
    ownerships_qs = (
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
        ownerships_qs = ownerships_qs.filter(owner=request.user)

    athletes = OwnershipService.get_owned_athletes(request.user)
    athletes = athletes.select_related("athleteprofile__guardian").prefetch_related(
        "roles", "team_memberships__team"
    )
    crew = ownerships_qs.exclude(user__roles__name="ATLETA").distinct()

    # --- Alerta de menores sin guardian ---
    minors_without_guardian_count = 0
    if is_headcoach or is_admin:
        minors_without_guardian_count = MinorAthleteService.get_minors_without_guardian(
            request.user
        ).count()

    # --- Lista de coaches para reasignación (solo ADMIN) ---
    available_coaches = None
    if is_admin:
        available_coaches = (
            User.objects.filter(
                roles__name__in=["HEADCOACH"],
                is_active=True,
            )
            .exclude(id=request.user.id)
            .distinct()
        )

    return render(
        request,
        "coach/manage_owned_users.html",
        {
            "athletes": athletes,
            "crew": crew,
            "is_admin": is_admin,
            "is_headcoach": is_headcoach,
            "available_coaches": available_coaches,
            "minors_without_guardian_count": minors_without_guardian_count,
        },
    )


# =============================================================================
# REMOVER USUARIO DEL OWNERSHIP
# =============================================================================


@role_required("HEADCOACH", "ADMIN")
def remove_owned_user(request, ownership_id):
    """
    Desactiva el ownership de un usuario.
    También desactiva sus membresías de equipo con el coach.

    Delega toda la lógica a OwnershipService.remove_from_ownership().
    """
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    try:
        ownership = OwnershipService.remove_from_ownership(
            ownership_id=ownership_id,
            removed_by=request.user,
        )
        messages.success(
            request,
            f"{ownership.user.get_full_name()} retirado de tu grupo correctamente.",
        )
    except ValidationError as e:
        messages.error(request, str(e))
    except PermissionDenied:
        messages.error(request, "No tienes permisos para realizar esta acción.")

    return redirect("coach:manage_owned_users")


# =============================================================================
# REASIGNAR USUARIO A OTRO COACH
# =============================================================================


@role_required("ADMIN")
def reassign_owned_user(request, ownership_id):
    """
    Transfiere el ownership de un usuario a otro coach.
    Solo ADMIN puede ejecutar esto.

    GET: Muestra formulario de selección de nuevo coach
    POST: Ejecuta la transferencia vía OwnershipService
    """
    try:
        ownership = UserOwnership.objects.select_related("owner", "user").get(
            id=ownership_id, is_active=True
        )
    except UserOwnership.DoesNotExist:
        messages.error(request, "Ownership no encontrado.")
        return redirect("coach:manage_owned_users")

    # Coaches disponibles (excluir el actual)
    available_coaches = (
        User.objects.filter(
            roles__name="HEADCOACH",
            is_active=True,
        )
        .exclude(id=ownership.owner_id)
        .distinct()
    )

    if request.method == "POST":
        new_owner_id = request.POST.get("new_owner_id")

        if not new_owner_id:
            messages.error(request, "Debes seleccionar un coach.")
            return redirect("coach:reassign_owned_user", ownership_id=ownership_id)

        new_owner = get_object_or_404(User, id=new_owner_id)

        try:
            new_ownership = OwnershipService.transfer_ownership(
                ownership_id=ownership_id,
                new_owner=new_owner,
                transferred_by=request.user,
            )
            messages.success(
                request,
                f"{new_ownership.user.get_full_name()} reasignado a "
                f"{new_owner.get_full_name()} correctamente.",
            )
            return redirect("coach:manage_owned_users")

        except (ValidationError, PermissionDenied) as e:
            messages.error(request, str(e))
            return redirect("coach:reassign_owned_user", ownership_id=ownership_id)

    return render(
        request,
        "coach/reassign_user.html",
        {
            "ownership": ownership,
            "available_coaches": available_coaches,
        },
    )


# =============================================================================
# EDITAR OWNERSHIP (solo cambiar datos — no reasignar coach)
# =============================================================================


@role_required("HEADCOACH", "ADMIN")
def edit_owned_user(request, ownership_id):
    """
    Edita datos de un ownership.
    HEADCOACH: solo puede editar ownerships propios (IDOR fix).
    ADMIN: puede editar cualquier ownership.
    """
    # --- IDOR fix: HEADCOACH solo ve sus propios ownerships ---
    if (
        not request.user.is_superuser
        and request.user.roles.filter(name="HEADCOACH").exists()
        and not request.user.roles.filter(name="ADMIN").exists()
    ):
        ownership = get_object_or_404(
            UserOwnership.objects.select_related("user", "owner"),
            id=ownership_id,
            is_active=True,
            owner=request.user,  # ← IDOR fix crítico
        )
    else:
        ownership = get_object_or_404(
            UserOwnership.objects.select_related("user", "owner"),
            id=ownership_id,
            is_active=True,
        )

    if request.method == "POST":
        action = request.POST.get("action")

        # Reasignación de coach: solo ADMIN
        if action == "change_owner":
            if not (
                request.user.is_superuser
                or request.user.roles.filter(name="ADMIN").exists()
            ):
                messages.error(
                    request, "Solo administradores pueden reasignar coaches."
                )
                return redirect("coach:manage_owned_users")

            # Redirigir a la view dedicada de reasignación
            return redirect("coach:reassign_owned_user", ownership_id=ownership.id)

        messages.error(request, "Acción no reconocida.")
        return redirect("coach:manage_owned_users")

    # Lista de coaches disponibles para reasignar (solo si es ADMIN)
    available_coaches = None
    if request.user.is_superuser or request.user.roles.filter(name="ADMIN").exists():
        available_coaches = (
            User.objects.filter(roles__name="HEADCOACH", is_active=True)
            .exclude(id=ownership.owner_id)
            .distinct()
        )

    return render(
        request,
        "coach/edit_owned_user.html",
        {
            "ownership": ownership,
            "available_coaches": available_coaches,
        },
    )


# =============================================================================
# GESTIONAR ATLETAS
# =============================================================================


@role_required("ADMIN", "HEADCOACH")
def manage_athletes(request):
    """
    Vista principal de gestión de atletas.
    Muestra:
    - Lista de atletas según rol del coach
    - Alerta de menores sin guardian
    - Formulario de creación rápida
    """
    can_create = request.user.roles.filter(name__in=["ADMIN", "HEADCOACH"]).exists()

    # --- Filtrar atletas según rol ---
    if request.user.roles.filter(name="HEADCOACH").exists():
        athletes = OwnershipService.get_owned_athletes(request.user)
    else:
        athletes = User.objects.filter(roles__name="ATLETA").distinct()

    # Enriquecer con datos de perfil y guardian
    athletes = athletes.select_related("athleteprofile__guardian").prefetch_related(
        "roles", "team_memberships__team"
    )

    # --- Menores sin guardian (alerta) ---
    minors_without_guardian = MinorAthleteService.get_minors_without_guardian(
        request.user
    )

    # --- Formulario de creación rápida ---
    form_crear = QuickAthleteRegisterForm()
    abrir_modal_crear = False

    if request.method == "POST":
        if "crear_alumno" in request.POST and can_create:
            form_crear = QuickAthleteRegisterForm(request.POST)

            if form_crear.is_valid():
                cd = form_crear.cleaned_data

                try:
                    with transaction.atomic():
                        # Generar username incremental seguro
                        max_num = (
                            User.objects.filter(username__startswith="ATHLETE-")
                            .annotate(
                                num=__import__(
                                    "django.db.models", fromlist=["functions"]
                                ).functions.Cast(
                                    __import__(
                                        "django.db.models", fromlist=["functions"]
                                    ).functions.Substr("username", 9),
                                    __import__(
                                        "django.db.models", fromlist=["IntegerField"]
                                    ).IntegerField(),
                                )
                            )
                            .aggregate(max_num=Max("num"))["max_num"]
                        ) or 0

                        username = f"ATHLETE-{max_num + 1}"

                        # Crear usuario base
                        new_user = User.objects.create_user(
                            username=username,
                            first_name=cd["first_name"],
                            last_name=cd["last_name"],
                            email=cd.get("email", ""),
                            phone=cd.get("phone") or None,
                            password=config(
                                "ATHLETE_TEMP_PASSWORD", default="$Temporal123"
                            ),
                            profile_completed=False,
                        )

                        # Asignar rol — la señal crea AthleteProfile automáticamente
                        new_user.roles.add(Role.objects.get(name="ATLETA"))

                        # Crear ownership vía servicio
                        OwnershipService.add_to_ownership(
                            owner=request.user,
                            user=new_user,
                            activated_by=request.user,
                        )

                    messages.success(
                        request,
                        f"Atleta creado: usuario {username}. "
                        f"Contraseña temporal: "
                        f"{config('ATHLETE_TEMP_PASSWORD', default='$Temporal123')}",
                    )

                    # Si el atleta es menor, alertar que necesita guardian
                    birth_date = cd.get("birth_date")
                    if birth_date and MinorAthleteService.is_minor(new_user):
                        messages.warning(
                            request,
                            f"⚠️ {new_user.get_full_name()} es menor de edad. "
                            "Debes asignarle un guardian.",
                        )
                        return redirect(
                            "accounts:assign_guardian",
                            athlete_id=new_user.id,
                        )

                    return redirect("coach:manage_athletes")

                except (ValidationError, Exception) as e:
                    messages.error(request, f"Error al crear atleta: {e}")
                    abrir_modal_crear = True

            else:
                abrir_modal_crear = True

    return render(
        request,
        "coach/athlete/manage_athletes.html",
        {
            "athletes": athletes,
            "form_crear": form_crear,
            "abrir_modal_crear": abrir_modal_crear,
            "can_create": can_create,
            "minors_without_guardian": minors_without_guardian,
            "minors_count": minors_without_guardian.count(),
        },
    )


# =============================================================================
# EDITAR MEDIDAS DE ATLETA
# =============================================================================


@role_required("ADMIN", "HEADCOACH")
def edit_athlete_measures(request, id):
    """
    Edita las medidas de perfil de un atleta.
    HEADCOACH: solo puede editar atletas que posee o están en su equipo.
    """
    athlete = get_object_or_404(User, id=id)

    # --- Validar acceso: HEADCOACH solo puede editar sus atletas ---
    if (
        not request.user.is_superuser
        and request.user.roles.filter(name="HEADCOACH").exists()
        and not request.user.roles.filter(name="ADMIN").exists()
    ):
        is_owner = OwnershipService.is_owned_by(owner=request.user, user=athlete)
        is_in_team = UserTeamMembership.objects.filter(
            user=athlete,
            team__coach=request.user,
            is_active=True,
        ).exists()

        if not (is_owner or is_in_team):
            messages.error(request, "No tienes acceso a este atleta.")
            return redirect("coach:manage_athletes")

    if request.method == "POST":
        form = DynamicMeasurementsForm(request.POST, user=athlete)

        if form.is_valid():
            for slug, value in form.cleaned_data.items():
                field = MeasurementField.objects.get(slug=slug)
                if value in ("", None):
                    MeasurementValue.objects.filter(user=athlete, field=field).delete()
                else:
                    MeasurementValue.objects.update_or_create(
                        user=athlete,
                        field=field,
                        defaults={"value": str(value)},
                    )
            messages.success(request, "Medidas actualizadas.")
            return redirect("coach:edit_athlete_measures", id=id)
    else:
        form = DynamicMeasurementsForm(user=athlete)

    # Información adicional para el template
    is_minor = MinorAthleteService.is_minor(athlete)
    guardian = MinorAthleteService.get_guardian(athlete) if is_minor else None

    return render(
        request,
        "coach/athlete/edit_measures.html",
        {
            "form": form,
            "athlete": athlete,
            "is_minor": is_minor,
            "guardian": guardian,
        },
    )


# =============================================================================
# TEAM MEMBERS — Agregar miembro existente
# =============================================================================


@role_required("ADMIN", "HEADCOACH")
def add_team_member(request, team_id):
    """
    Agrega un usuario existente al equipo.
    POST only.
    """
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    team = get_object_or_404(Team, id=team_id, is_active=True)
    _validate_team_access(request.user, team)

    user_id = request.POST.get("user_id")
    role_in_team = request.POST.get("role_in_team", "ATLETA")

    if role_in_team not in dict(UserTeamMembership.ROLE_CHOICES):
        messages.error(request, "Rol de equipo inválido.")
        return redirect("coach:manage_team_members", team_id=team.id)

    # HEADCOACH solo puede agregar sus own users
    if request.user.roles.filter(name="HEADCOACH").exists():
        target_user = get_object_or_404(
            User,
            id=user_id,
            owner_links__owner=request.user,
            owner_links__is_active=True,
        )
    else:
        target_user = get_object_or_404(User, id=user_id)

    if not _can_assume_team_role(target_user, role_in_team):
        messages.warning(
            request,
            f"El rol global de {target_user.get_full_name()} no coincide con "
            f"'{role_in_team}'. Agregado de todas formas — verifica que sea intencional.",
        )

    membership, _ = UserTeamMembership.objects.get_or_create(
        user=target_user, team=team
    )
    membership.activate(role=role_in_team)

    messages.success(request, f"{target_user.get_full_name()} agregado al equipo.")
    return redirect("coach:manage_team_members", team_id=team.id)


# =============================================================================
# TEAM CREW — Crear nuevo staff
# =============================================================================


@role_required("HEADCOACH", "ADMIN")
def create_team_crew_member(request, team_id):
    """
    Crea un nuevo usuario de staff y lo agrega al equipo.
    Si el email ya existe, reutiliza el usuario.
    """
    team = get_object_or_404(Team, id=team_id, is_active=True)
    _validate_team_access(request.user, team)

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
            return redirect("coach:create_team_crew_member", team_id=team.id)

        global_role = get_object_or_404(
            Role, id=global_role_id, name__in=["COACH", "STAFF"]
        )

        if team_role not in dict(UserTeamMembership.ROLE_CHOICES):
            messages.error(request, "Rol de equipo inválido.")
            return redirect("coach:create_team_crew_member", team_id=team.id)

        try:
            with transaction.atomic():
                # Buscar o crear usuario por email
                new_user, created = User.objects.get_or_create(
                    email=email,
                    defaults={
                        "username": _generate_unique_username(email),
                        "first_name": first_name,
                        "last_name": last_name,
                        "is_active": True,
                        "profile_completed": False,
                    },
                )

                temp_password = None
                if created:
                    temp_password = _generate_temp_password()
                    new_user.set_password(temp_password)
                    new_user.save()
                    messages.info(
                        request,
                        f"Usuario nuevo creado para {email}. "
                        "Contraseña temporal generada.",
                    )
                else:
                    if (
                        new_user.first_name != first_name
                        or new_user.last_name != last_name
                    ):
                        messages.warning(
                            request,
                            f"Usuario existente como {new_user.get_full_name()}. "
                            "No se modificó el nombre.",
                        )

                # Ownership vía servicio
                OwnershipService.add_to_ownership(
                    owner=request.user,
                    user=new_user,
                    activated_by=request.user,
                )

                # Rol global
                if not new_user.roles.filter(id=global_role.id).exists():
                    new_user.roles.add(global_role)

                # Membership en equipo
                membership, _ = UserTeamMembership.objects.get_or_create(
                    user=new_user, team=team
                )
                membership.activate(role=team_role)

        except Exception as e:
            messages.error(request, f"Error al crear miembro: {e}")
            return redirect("coach:create_team_crew_member", team_id=team.id)

        action_word = "creado" if created else "agregado"
        messages.success(
            request,
            f"{new_user.get_full_name()} {action_word} al equipo correctamente.",
        )
        return redirect("coach:manage_team_members", team_id=team.id)

    return render(
        request,
        "coach/crew/create_crew_member.html",
        {
            "team": team,
            "global_roles": allowed_global_roles,
            "team_roles": allowed_team_roles,
        },
    )


# =============================================================================
# TEAM MEMBERS — Cambiar rol
# =============================================================================


@role_required("ADMIN", "HEADCOACH")
def change_team_role(request, membership_id):
    """Cambia el rol de un usuario dentro del equipo."""
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    membership = get_object_or_404(UserTeamMembership, id=membership_id)

    if request.user.roles.filter(name="HEADCOACH").exists():
        if membership.team.coach != request.user:
            raise PermissionDenied

    new_role = request.POST.get("role_in_team")
    if new_role not in dict(UserTeamMembership.ROLE_CHOICES):
        messages.error(request, "Rol inválido.")
        return redirect("coach:manage_team_members", team_id=membership.team.id)

    if not _can_assume_team_role(membership.user, new_role):
        messages.warning(
            request,
            f"El rol global de {membership.user.get_full_name()} no coincide con "
            f"'{new_role}'. Cambiado de todas formas.",
        )

    membership.activate(role=new_role)
    messages.success(request, "Rol actualizado.")
    return redirect("coach:manage_team_members", team_id=membership.team.id)


# =============================================================================
# TEAM MEMBERS — Retirar miembro
# =============================================================================


@role_required("ADMIN", "HEADCOACH")
def remove_team_member(request, membership_id):
    """Retira un miembro del equipo (desactiva membership)."""
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    membership = get_object_or_404(UserTeamMembership, id=membership_id)

    if request.user.roles.filter(name="HEADCOACH").exists():
        if membership.team.coach != request.user:
            raise PermissionDenied

    nombre = membership.user.get_full_name()
    membership.deactivate()
    messages.success(request, f"{nombre} retirado del equipo.")
    return redirect("coach:manage_team_members", team_id=membership.team.id)

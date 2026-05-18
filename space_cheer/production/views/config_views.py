import logging
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import role_required
from accounts.models import Role
from production.models import (
    OperarioRoleAssignment,
    ProductionRole,
    ProductionStage,
)

logger = logging.getLogger(__name__)
User = get_user_model()


@role_required("ADMIN")
def manage_stages(request):
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        slug = request.POST.get("slug", "").strip()
        icon = request.POST.get("icon", "").strip()
        try:
            display_order = int(request.POST.get("display_order", 0))
        except (ValueError, TypeError):
            display_order = 0
        description = request.POST.get("description", "").strip()
        if name and slug:
            stage_id = request.POST.get("stage_id")
            if stage_id:
                stage = get_object_or_404(ProductionStage, pk=stage_id)
                stage.name = name
                stage.slug = slug
                stage.icon = icon
                stage.display_order = display_order
                stage.description = description
                stage.save()
                messages.success(request, "Etapa actualizada.")
            else:
                ProductionStage.objects.create(
                    name=name,
                    slug=slug,
                    icon=icon,
                    display_order=display_order,
                    description=description,
                )
                messages.success(request, "Etapa creada.")
        else:
            messages.error(request, "Nombre y slug son obligatorios.")
        return redirect("production:manage_stages")

    stages = ProductionStage.objects.all()
    return render(request, "production/config/stages.html", {"stages": stages})


@role_required("ADMIN")
def manage_roles(request):
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        stage_ids = request.POST.getlist("stages")
        if name:
            role_id = request.POST.get("role_id")
            if role_id:
                prod_role = get_object_or_404(ProductionRole, pk=role_id)
                prod_role.name = name
                prod_role.save()
                prod_role.stages.set(stage_ids)
                messages.success(request, "Rol actualizado.")
            else:
                prod_role = ProductionRole.objects.create(
                    name=name, created_by=request.user
                )
                prod_role.stages.set(stage_ids)
                messages.success(request, "Rol de producción creado.")
        else:
            messages.error(request, "El nombre es obligatorio.")
        return redirect("production:manage_roles")

    roles = ProductionRole.objects.prefetch_related("stages").all()
    stages = ProductionStage.objects.all()
    return render(request, "production/config/roles.html", {
        "roles": roles,
        "stages": stages,
    })


@role_required("ADMIN")
def manage_role_operarios(request, pk):
    prod_role = get_object_or_404(ProductionRole, pk=pk)

    if request.method == "POST":
        action = request.POST.get("action")
        operario_id = request.POST.get("operario_id")
        if operario_id:
            try:
                operario = User.objects.get(pk=operario_id, roles__name="OPERARIO", is_active=True)
                if action == "assign":
                    OperarioRoleAssignment.objects.get_or_create(
                        user=operario,
                        role=prod_role,
                        defaults={"assigned_by": request.user},
                    )
                    messages.success(request, f"Rol asignado a {operario.get_full_name() or operario.username}.")
                elif action == "remove":
                    OperarioRoleAssignment.objects.filter(user=operario, role=prod_role).delete()
                    messages.success(request, f"Rol removido de {operario.get_full_name() or operario.username}.")
            except User.DoesNotExist:
                messages.error(request, "Operario no encontrado.")
        return redirect("production:manage_role_operarios", pk=pk)

    assigned_ids = set(
        OperarioRoleAssignment.objects.filter(role=prod_role).values_list("user_id", flat=True)
    )
    all_operarios = User.objects.filter(roles__name="OPERARIO", is_active=True).distinct()
    return render(request, "production/config/assign_roles.html", {
        "prod_role": prod_role,
        "all_operarios": all_operarios,
        "assigned_ids": assigned_ids,
    })


@role_required("ADMIN")
def manage_operarios(request):
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        first_name = request.POST.get("first_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "").strip()
        if username and password:
            if User.objects.filter(username=username).exists():
                messages.error(request, f"El usuario '{username}' ya existe.")
            else:
                op_role, _ = Role.objects.get_or_create(
                    name="OPERARIO", defaults={"is_production_type": True}
                )
                user = User.objects.create_user(
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    email=email,
                    password=password,
                )
                user.profile_completed = True
                user.save(update_fields=["profile_completed"])
                user.roles.add(op_role)
                messages.success(request, f"Operario '{username}' creado.")
        else:
            messages.error(request, "Usuario y contraseña son obligatorios.")
        return redirect("production:manage_operarios")

    operarios = User.objects.filter(roles__name="OPERARIO", is_active=True).distinct()
    return render(request, "production/config/operarios.html", {"operarios": operarios})


@role_required("ADMIN")
def operario_detail(request, pk):
    operario = get_object_or_404(
        User.objects.filter(roles__name="OPERARIO", is_active=True), pk=pk
    )

    if request.method == "POST":
        action = request.POST.get("action")
        role_id = request.POST.get("role_id")
        if role_id:
            try:
                prod_role = ProductionRole.objects.get(pk=role_id)
                if action == "assign":
                    OperarioRoleAssignment.objects.get_or_create(
                        user=operario,
                        role=prod_role,
                        defaults={"assigned_by": request.user},
                    )
                    messages.success(request, f"Rol '{prod_role.name}' asignado.")
                elif action == "remove":
                    OperarioRoleAssignment.objects.filter(
                        user=operario, role=prod_role
                    ).delete()
                    messages.success(request, f"Rol '{prod_role.name}' removido.")
            except ProductionRole.DoesNotExist:
                messages.error(request, "Rol no encontrado.")
        return redirect("production:operario_detail", pk=pk)

    assigned_role_ids = set(
        OperarioRoleAssignment.objects.filter(user=operario).values_list("role_id", flat=True)
    )
    prod_roles = ProductionRole.objects.prefetch_related("stages").all()
    return render(request, "production/config/operario_detail.html", {
        "operario": operario,
        "prod_roles": prod_roles,
        "assigned_role_ids": assigned_role_ids,
    })

import logging
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db.models import Count, Max, Q
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import role_required
from production.models import (
    OperarioRoleAssignment,
    ProductionRole,
    ProductionStage,
    ProductionTask,
)
from production.services import OperarioService

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
                    OperarioService.assign_role(operario, prod_role, request.user)
                    messages.success(request, f"Rol asignado a {operario.get_full_name() or operario.username}.")
                elif action == "remove":
                    OperarioService.remove_role(operario, prod_role)
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
        action = request.POST.get("action", "create")

        if action == "reactivate":
            op_id = request.POST.get("operario_id")
            try:
                op = User.objects.get(pk=op_id, roles__name="OPERARIO")
                op.is_active = True
                op.save(update_fields=["is_active"])
                messages.success(request, f"Operario '{op.username}' reactivado.")
            except User.DoesNotExist:
                messages.error(request, "Operario no encontrado.")
            return redirect("production:manage_operarios")

        if action == "assign_existing":
            user_id = request.POST.get("user_id")
            try:
                user = User.objects.get(pk=user_id, is_superuser=False)
                OperarioService.assign_existing(user)
                messages.success(request, f"'{user.get_full_name() or user.username}' ahora es operario.")
            except User.DoesNotExist:
                messages.error(request, "Usuario no encontrado.")
            except ValueError as exc:
                messages.error(request, str(exc))
            return redirect("production:manage_operarios")

        # create
        username = request.POST.get("username", "").strip()
        first_name = request.POST.get("first_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "").strip()
        if username and password:
            try:
                OperarioService.create(
                    username=username,
                    password=password,
                    first_name=first_name,
                    last_name=last_name,
                    email=email,
                )
                messages.success(request, f"Operario '{username}' creado.")
            except ValueError as exc:
                messages.error(request, str(exc))
        else:
            messages.error(request, "Usuario y contraseña son obligatorios.")
        return redirect("production:manage_operarios")

    operarios = User.objects.filter(roles__name="OPERARIO", is_active=True).distinct()
    inactive_operarios = User.objects.filter(roles__name="OPERARIO", is_active=False).distinct()

    # Búsqueda de usuarios existentes para asignar
    search_query = request.GET.get("q", "").strip()
    search_results = None
    if search_query:
        operario_ids = User.objects.filter(roles__name="OPERARIO").values_list("pk", flat=True)
        search_results = (
            User.objects.filter(
                Q(username__icontains=search_query)
                | Q(first_name__icontains=search_query)
                | Q(last_name__icontains=search_query)
                | Q(email__icontains=search_query),
                is_superuser=False,
            )
            .exclude(pk__in=operario_ids)
            .prefetch_related("roles")
            .order_by("first_name", "last_name")[:20]
        )

    return render(request, "production/config/operarios.html", {
        "operarios": operarios,
        "inactive_operarios": inactive_operarios,
        "search_results": search_results,
        "search_query": search_query,
    })


@role_required("ADMIN")
def operario_detail(request, pk):
    operario = get_object_or_404(
        User.objects.filter(roles__name="OPERARIO"), pk=pk
    )

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "edit":
            operario.first_name = request.POST.get("first_name", "").strip()
            operario.last_name = request.POST.get("last_name", "").strip()
            operario.email = request.POST.get("email", "").strip()
            operario.save(update_fields=["first_name", "last_name", "email"])
            messages.success(request, "Datos actualizados.")
            return redirect("production:operario_detail", pk=pk)

        if action == "deactivate":
            operario.is_active = False
            operario.save(update_fields=["is_active"])
            messages.success(request, f"Operario '{operario.username}' desactivado.")
            return redirect("production:manage_operarios")

        if action == "reactivate":
            operario.is_active = True
            operario.save(update_fields=["is_active"])
            messages.success(request, f"Operario '{operario.username}' reactivado.")
            return redirect("production:operario_detail", pk=pk)

        if action == "reset_password":
            new_password = request.POST.get("new_password", "").strip()
            try:
                validate_password(new_password, user=operario)
                operario.set_password(new_password)
                operario.save(update_fields=["password"])
                messages.success(request, "Contraseña actualizada.")
            except ValidationError as exc:
                for err in exc.messages:
                    messages.error(request, err)
            return redirect("production:operario_detail", pk=pk)

        # assign / remove role
        role_id = request.POST.get("role_id")
        if role_id:
            try:
                prod_role = ProductionRole.objects.get(pk=role_id)
                if action == "assign":
                    OperarioService.assign_role(operario, prod_role, request.user)
                    messages.success(request, f"Rol '{prod_role.name}' asignado.")
                elif action == "remove":
                    OperarioService.remove_role(operario, prod_role)
                    messages.success(request, f"Rol '{prod_role.name}' removido.")
            except ProductionRole.DoesNotExist:
                messages.error(request, "Rol no encontrado.")
        return redirect("production:operario_detail", pk=pk)

    assigned_role_ids = set(
        OperarioRoleAssignment.objects.filter(user=operario).values_list("role_id", flat=True)
    )
    prod_roles = ProductionRole.objects.prefetch_related("stages").all()

    task_stats = ProductionTask.objects.filter(completed_by=operario).aggregate(
        total_completed=Count("pk"),
        last_activity=Max("completed_at"),
    )
    pending_count = ProductionTask.objects.filter(
        assigned_to=operario, status=ProductionTask.Status.PENDING
    ).count()
    recent_tasks = (
        ProductionTask.objects.filter(completed_by=operario)
        .select_related("stage", "job__order", "order_item__product")
        .order_by("-completed_at")[:10]
    )

    return render(request, "production/config/operario_detail.html", {
        "operario": operario,
        "prod_roles": prod_roles,
        "assigned_role_ids": assigned_role_ids,
        "task_stats": task_stats,
        "pending_count": pending_count,
        "recent_tasks": recent_tasks,
    })

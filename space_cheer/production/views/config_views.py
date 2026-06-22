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
    ProductionTemplate,
    ProductionTemplateStage,
    ProductStageConfig,
    StageResponsibility,
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


@role_required("ADMIN")
def product_stages_matrix(request):
    from products.models import Product

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "apply_template":
            product_id = request.POST.get("product_id")
            template_id = request.POST.get("template_id")
            merge_mode = request.POST.get("merge_mode", "replace")
            try:
                product = Product.objects.get(pk=product_id, is_active=True)
                template = ProductionTemplate.objects.prefetch_related(
                    "template_stages__stage"
                ).get(pk=template_id)
            except (Product.DoesNotExist, ProductionTemplate.DoesNotExist):
                messages.error(request, "Producto o plantilla no encontrados.")
                return redirect("production:product_stages_matrix")

            if merge_mode == "replace":
                ProductStageConfig.objects.filter(product=product).delete()
                for ts in template.template_stages.all():
                    ProductStageConfig.objects.create(
                        product=product,
                        stage=ts.stage,
                        display_order=ts.display_order,
                    )
                messages.success(
                    request,
                    f"Plantilla '{template.name}' aplicada a '{product.name}' (reemplazar).",
                )
            else:  # merge
                existing_stage_ids = set(
                    ProductStageConfig.objects.filter(product=product).values_list(
                        "stage_id", flat=True
                    )
                )
                created = 0
                for ts in template.template_stages.all():
                    if ts.stage_id not in existing_stage_ids:
                        ProductStageConfig.objects.create(
                            product=product,
                            stage=ts.stage,
                            display_order=ts.display_order,
                        )
                        created += 1
                messages.success(
                    request,
                    f"Plantilla '{template.name}' fusionada con '{product.name}' ({created} etapa(s) añadida(s)).",
                )
            return redirect("production:product_stages_matrix")

        if action == "add_stage":
            product_id = request.POST.get("product_id")
            stage_id = request.POST.get("stage_id")
            try:
                display_order = int(request.POST.get("display_order", 0))
            except (ValueError, TypeError):
                display_order = 0
            try:
                product = Product.objects.get(pk=product_id, is_active=True)
                stage = ProductionStage.objects.get(pk=stage_id)
            except (Product.DoesNotExist, ProductionStage.DoesNotExist):
                messages.error(request, "Producto o etapa no encontrados.")
                return redirect("production:product_stages_matrix")
            _, created = ProductStageConfig.objects.get_or_create(
                product=product,
                stage=stage,
                defaults={"display_order": display_order},
            )
            if created:
                messages.success(
                    request, f"Etapa '{stage.name}' añadida a '{product.name}'."
                )
            else:
                messages.info(
                    request,
                    f"'{product.name}' ya tiene la etapa '{stage.name}'.",
                )
            return redirect("production:product_stages_matrix")

        if action == "remove_stage":
            product_id = request.POST.get("product_id")
            stage_id = request.POST.get("stage_id")
            deleted, _ = ProductStageConfig.objects.filter(
                product_id=product_id, stage_id=stage_id
            ).delete()
            if deleted:
                messages.success(request, "Etapa quitada del producto.")
            return redirect("production:product_stages_matrix")

        messages.error(request, "Acción no reconocida.")
        return redirect("production:product_stages_matrix")

    # GET
    all_stages = ProductionStage.objects.order_by("display_order", "name")
    products = (
        Product.objects.filter(is_active=True)
        .prefetch_related("stage_configs__stage")
        .order_by("name")
    )
    templates = ProductionTemplate.objects.prefetch_related(
        "template_stages__stage"
    ).order_by("name")

    products_data = []
    for product in products:
        configured_stage_ids = {sc.stage_id for sc in product.stage_configs.all()}
        available_stages = [s for s in all_stages if s.pk not in configured_stage_ids]
        products_data.append(
            {
                "product": product,
                "stage_configs": sorted(
                    product.stage_configs.all(), key=lambda sc: sc.display_order
                ),
                "configured_stage_ids": configured_stage_ids,
                "available_stages": available_stages,
            }
        )

    return render(
        request,
        "production/config/product_stages_matrix.html",
        {
            "products_data": products_data,
            "all_stages": all_stages,
            "templates": templates,
        },
    )


@role_required("ADMIN")
def manage_responsibilities(request):
    if request.method == "POST":
        stage_id = request.POST.get("stage_id")
        responsible_role_id = request.POST.get("responsible_role_id")
        auxiliary_role_ids = request.POST.getlist("auxiliary_role_ids")

        if stage_id and responsible_role_id:
            stage = get_object_or_404(ProductionStage, pk=stage_id)
            responsible_role = get_object_or_404(ProductionRole, pk=responsible_role_id)
            responsibility, created = StageResponsibility.objects.update_or_create(
                stage=stage,
                defaults={"responsible_role": responsible_role},
            )
            responsibility.auxiliary_roles.set(auxiliary_role_ids)
            if created:
                messages.success(request, f"Responsabilidad asignada a la etapa '{stage.name}'.")
            else:
                messages.success(request, f"Responsabilidad de '{stage.name}' actualizada.")
        else:
            messages.error(request, "La etapa y el rol responsable son obligatorios.")

        return redirect("production:manage_responsibilities")

    stages = ProductionStage.objects.prefetch_related(
        "responsibility__responsible_role",
        "responsibility__auxiliary_roles",
    ).order_by("display_order", "name")
    roles = ProductionRole.objects.all().order_by("name")

    return render(request, "production/config/responsabilidades.html", {
        "stages": stages,
        "roles": roles,
    })


@role_required("ADMIN")
def manage_templates(request):
    if request.method == "POST":
        action = request.POST.get("action", "")

        if action == "create":
            name = request.POST.get("name", "").strip()
            description = request.POST.get("description", "").strip()
            if name:
                ProductionTemplate.objects.create(
                    name=name,
                    description=description,
                    created_by=request.user,
                )
                messages.success(request, "Plantilla creada.")
            else:
                messages.error(request, "El nombre de la plantilla es obligatorio.")

        elif action == "add_stage":
            template_id = request.POST.get("template_id")
            stage_id = request.POST.get("stage_id")
            try:
                display_order = int(request.POST.get("display_order", 0))
            except (ValueError, TypeError):
                display_order = 0
            if template_id and stage_id:
                template = get_object_or_404(ProductionTemplate, pk=template_id)
                stage = get_object_or_404(ProductionStage, pk=stage_id)
                _, created = ProductionTemplateStage.objects.get_or_create(
                    template=template,
                    stage=stage,
                    defaults={"display_order": display_order},
                )
                if created:
                    messages.success(request, f"Etapa '{stage.name}' agregada a la plantilla.")
                else:
                    messages.error(request, "Esa etapa ya está en la plantilla.")
            else:
                messages.error(request, "Plantilla y etapa son obligatorias.")

        elif action == "remove_stage":
            template_id = request.POST.get("template_id")
            stage_id = request.POST.get("stage_id")
            if template_id and stage_id:
                deleted, _ = ProductionTemplateStage.objects.filter(
                    template_id=template_id, stage_id=stage_id
                ).delete()
                if deleted:
                    messages.success(request, "Etapa eliminada de la plantilla.")
                else:
                    messages.error(request, "No se encontró esa etapa en la plantilla.")
            else:
                messages.error(request, "Plantilla y etapa son obligatorias.")

        elif action == "delete_template":
            template_id = request.POST.get("template_id")
            template = get_object_or_404(ProductionTemplate, pk=template_id)
            stage_ids = template.stages.values_list("pk", flat=True)
            if ProductStageConfig.objects.filter(stage__in=stage_ids).exists():
                messages.error(
                    request,
                    f"No se puede eliminar '{template.name}': sus etapas están en uso por uno o más productos.",
                )
            else:
                template.delete()
                messages.success(request, "Plantilla eliminada.")

        return redirect("production:manage_templates")

    templates = ProductionTemplate.objects.prefetch_related(
        "template_stages__stage"
    ).order_by("name")
    all_stages = ProductionStage.objects.order_by("display_order", "name")

    return render(request, "production/config/plantillas.html", {
        "templates": templates,
        "all_stages": all_stages,
    })

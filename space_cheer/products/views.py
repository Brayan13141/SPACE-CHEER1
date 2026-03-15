from django.contrib import messages
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.db.models import Count
from django.db.models import ProtectedError
from products.models import Product, ProductSizeVariant, ProductMeasurementField
from products.forms import ProductForm
from products.product_templates import PRODUCT_TEMPLATES
from measures.models import MeasurementField


# ─────────────────────────────────────────────────────────────────────────────
# 1. LISTA
# ─────────────────────────────────────────────────────────────────────────────
@login_required
def product_list(request):

    products = (
        Product.objects.select_related("season", "owner_team")
        .annotate(
            measurement_count=Count("measurement_fields", distinct=True),
            size_count=Count("size_variants", distinct=True),
        )
        .order_by("name")
    )
    # Filtros opcionales
    active_filter = request.GET.get("active", "")
    type_filter = request.GET.get("type", "")
    search = request.GET.get("q", "").strip()

    if active_filter == "1":
        products = products.filter(is_active=True)
    elif active_filter == "0":
        products = products.filter(is_active=False)

    if type_filter:
        products = products.filter(product_type=type_filter)

    if search:
        products = products.filter(name__icontains=search)

    return render(
        request,
        "products/product_list.html",
        {
            "products": products,
            "active_filter": active_filter,
            "type_filter": type_filter,
            "search": search,
            "type_choices": Product.PRODUCT_TYPE_CHOICES,
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# 2. CREAR — paso 1: seleccionar plantilla
# ─────────────────────────────────────────────────────────────────────────────


@login_required
@permission_required("products.add_product", raise_exception=True)
def product_create_select_type(request):

    return render(
        request,
        "products/product_template_select.html",
        {
            "templates": PRODUCT_TEMPLATES,
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# 3. CREAR — paso 2: formulario
# ─────────────────────────────────────────────────────────────────────────────


@login_required
@permission_required("products.add_product", raise_exception=True)
def product_create(request):

    template_key = request.GET.get("template") or request.POST.get("template")
    template = PRODUCT_TEMPLATES.get(template_key)
    initial_data = template.get("defaults", {}) if template else {}

    if request.method == "POST":

        form = ProductForm(request.POST, request.FILES, template_key=template_key)

        if form.is_valid():
            product = form.save(commit=False)

            # Forzar valores desde la plantilla — no confiar en el POST
            if template:
                defaults = template["defaults"]
                product.product_type = defaults["product_type"]
                product.usage_type = defaults["usage_type"]
                product.scope = defaults["scope"]
                product.size_strategy = defaults["size_strategy"]

            product.save()
            messages.success(request, f"Producto '{product.name}' creado.")
            return redirect("products:product_detail", product_id=product.id)

    else:
        form = ProductForm(initial=initial_data, template_key=template_key)

    return render(
        request,
        "products/product_form.html",
        {
            "form": form,
            "title": "Crear producto",
            "template_key": template_key,
            "template": template,
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# 4. DETALLE — editar info, toggle activo, tallas y medidas en una sola vista
# ─────────────────────────────────────────────────────────────────────────────


@login_required
@permission_required("products.change_product", raise_exception=True)
def product_detail(request, product_id):

    product = get_object_or_404(
        Product.objects.select_related("season", "owner_team").prefetch_related(
            "measurement_fields__field", "size_variants"
        ),
        pk=product_id,
    )

    if request.method == "POST":
        action = request.POST.get("action")

        # ── Editar información básica ──────────────────────────────────────
        if action == "edit_info":
            form = ProductForm(request.POST, request.FILES, instance=product)
            if form.is_valid():
                form.save()
                messages.success(request, "Producto actualizado.")
            else:
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f"{field}: {error}")
            return redirect("products:product_detail", product_id=product.id)

        # ── Toggle activo / inactivo ───────────────────────────────────────
        elif action == "toggle_active":
            product.is_active = not product.is_active
            product.save(update_fields=["is_active"])
            estado = "activado" if product.is_active else "desactivado"
            messages.success(request, f"Producto {estado}.")
            return redirect("products:product_detail", product_id=product.id)

        # ── Agregar talla ──────────────────────────────────────────────────
        elif action == "add_size":
            size = request.POST.get("size", "").strip().upper()
            price = request.POST.get("additional_price") or "0"

            if not size:
                messages.error(request, "Ingresa una talla.")
            elif ProductSizeVariant.objects.filter(product=product, size=size).exists():
                messages.error(request, f"La talla '{size}' ya existe.")
            else:
                try:
                    ProductSizeVariant.objects.create(
                        product=product,
                        size=size,
                        additional_price=float(price),
                    )
                    product.update_configuration_status()
                    messages.success(request, f"Talla '{size}' agregada.")
                except Exception as e:
                    messages.error(request, str(e))

            return redirect("products:product_detail", product_id=product.id)

        # ── Eliminar talla ─────────────────────────────────────────────────
        elif action == "remove_size":
            size_id = request.POST.get("size_id")
            variant = get_object_or_404(ProductSizeVariant, pk=size_id, product=product)
            nombre = variant.size

            try:
                variant.delete()
                product.update_configuration_status()
                messages.success(request, f"Talla '{nombre}' eliminada.")
            except ProtectedError as e:
                # Contar cuántas órdenes la usan para dar contexto
                orders_count = len(e.protected_objects)
                messages.error(
                    request,
                    f"No se puede eliminar la talla '{nombre}' porque está siendo "
                    f"usada en {orders_count} item(s) de órdenes existentes. "
                    f"Solo puedes eliminarla cuando no haya órdenes activas que la referencien.",
                )

            return redirect("products:product_detail", product_id=product.id)

        # ── Agregar campo de medida ────────────────────────────────────────
        elif action == "add_measurement":
            field_id = request.POST.get("field_id")
            required = request.POST.get("required") == "on"

            if not field_id:
                messages.error(request, "Selecciona un campo.")
                return redirect("products:product_detail", product_id=product.id)

            field = get_object_or_404(MeasurementField, pk=field_id)

            if ProductMeasurementField.objects.filter(
                product=product, field=field
            ).exists():
                messages.warning(request, f"'{field.name}' ya está en este producto.")
            else:
                ProductMeasurementField.objects.create(
                    product=product,
                    field=field,
                    required=required,
                )
                product.update_configuration_status()
                messages.success(request, f"Campo '{field.name}' agregado.")

            return redirect("products:product_detail", product_id=product.id)

        # ── Eliminar campo de medida ───────────────────────────────────────
        elif action == "remove_measurement":
            field_id = request.POST.get("field_id")
            pmf = get_object_or_404(
                ProductMeasurementField, product=product, field_id=field_id
            )
            nombre = pmf.field.name

            try:
                pmf.delete()
                product.update_configuration_status()
                messages.success(request, f"Campo '{nombre}' eliminado.")
            except ProtectedError as e:
                orders_count = len(e.protected_objects)
                messages.error(
                    request,
                    f"No se puede eliminar el campo '{nombre}' porque está referenciado "
                    f"en {orders_count} medida(s) de órdenes existentes.",
                )

            return redirect("products:product_detail", product_id=product.id)

    # ── GET ────────────────────────────────────────────────────────────────
    used_field_ids = product.measurement_fields.values_list("field_id", flat=True)
    available_fields = MeasurementField.objects.exclude(id__in=used_field_ids)
    form = ProductForm(instance=product)

    return render(
        request,
        "products/product_detail.html",
        {
            "product": product,
            "form": form,
            "measurement_fields": product.measurement_fields.select_related("field"),
            "size_variants": product.size_variants.all(),
            "available_fields": available_fields,
        },
    )

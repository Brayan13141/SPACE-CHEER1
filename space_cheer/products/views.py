from django.contrib import messages
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.db.models import Count
from products.models import Product
from products.forms import ProductForm
from products.product_templates import PRODUCT_TEMPLATES
from measures.models import MeasurementField
from django.db.models import Q, Min, Max
from products.models import ProductSizeVariant, ProductMeasurementField
from django.db.models import ProtectedError


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
        post_data = request.POST.copy()

        # Forzar los campos de la plantilla si existen
        if template:
            defaults = template.get("defaults", {})
            for field_name in ["product_type", "usage_type", "size_strategy", "scope"]:
                post_data[field_name] = defaults[field_name]

        # Creamos el formulario con POST modificado
        form = ProductForm(post_data, request.FILES, template_key=template_key)

        if form.is_valid():
            product = form.save(commit=False)
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
    # Obtenemos el producto con relaciones optimizadas
    product = get_object_or_404(
        Product.objects.select_related("season", "owner_team")
        .prefetch_related("size_variants", "measurement_fields__field")
        .annotate(
            orders_count=Count("orderitem", distinct=True),
            active_orders_count=Count(
                "orderitem",
                filter=~Q(orderitem__order__status__in=["DELIVERED", "CANCELLED"]),
                distinct=True,
            ),
        ),
        pk=product_id,
    )
    print(
        f"Producto '{product.name}' tiene {product.orders_count} orden(es) asociada(s), de las cuales {product.active_orders_count} están activas."
    )
    # Flags para el template
    requires_sizes = product.requires_sizes
    requires_measurements = product.requires_measurements
    requires_design = product.requires_design

    # Procesamos POST
    if request.method == "POST":
        action = request.POST.get("action")

        # ── Editar producto ──────────────────────────────
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

        # ── Toggle activo / inactivo ───────────────────
        elif action == "toggle_active":
            product.is_active = not product.is_active
            product.save(update_fields=["is_active"])
            estado = "activado" if product.is_active else "desactivado"
            messages.success(request, f"Producto {estado}.")
            return redirect("products:product_detail", product_id=product.id)

        # ── Agregar talla ──────────────────────────────
        elif action == "add_size" and requires_sizes:
            size = request.POST.get("size", "").strip().upper()
            price = request.POST.get("additional_price") or "0"

            if not size:
                messages.error(request, "Ingresa una talla.")
            elif ProductSizeVariant.objects.filter(product=product, size=size).exists():
                messages.error(request, f"La talla '{size}' ya existe.")
            else:
                ProductSizeVariant.objects.create(
                    product=product,
                    size=size,
                    additional_price=float(price),
                )
                product.update_configuration_status()
                messages.success(request, f"Talla '{size}' agregada.")
            return redirect("products:product_detail", product_id=product.id)

        # ── Eliminar talla ─────────────────────────────
        elif action == "remove_size" and requires_sizes:
            size_id = request.POST.get("size_id")
            variant = get_object_or_404(ProductSizeVariant, pk=size_id, product=product)
            try:
                variant.delete()
                product.update_configuration_status()
                messages.success(request, f"Talla '{variant.size}' eliminada.")
            except ProtectedError as e:
                messages.error(
                    request,
                    f"No se puede eliminar la talla '{variant.size}' porque está usada en {len(e.protected_objects)} orden(es).",
                )
            return redirect("products:product_detail", product_id=product.id)

        # ── Agregar campo de medida ────────────────────
        elif action == "add_measurement" and requires_measurements:
            field_id = request.POST.get("field_id")
            required = request.POST.get("required") == "on"
            if not field_id:
                messages.error(request, "Selecciona un campo.")
            else:
                field = get_object_or_404(MeasurementField, pk=field_id)
                if ProductMeasurementField.objects.filter(
                    product=product, field=field
                ).exists():
                    messages.warning(
                        request, f"'{field.name}' ya está en este producto."
                    )
                else:
                    ProductMeasurementField.objects.create(
                        product=product, field=field, required=required
                    )
                    product.update_configuration_status()
                    messages.success(request, f"Campo '{field.name}' agregado.")
            return redirect("products:product_detail", product_id=product.id)

        # ── Eliminar campo de medida ──────────────────
        elif action == "remove_measurement" and requires_measurements:
            field_id = request.POST.get("field_id")
            pmf = get_object_or_404(
                ProductMeasurementField, product=product, field_id=field_id
            )
            try:
                pmf.delete()
                product.update_configuration_status()
                messages.success(request, f"Campo '{pmf.field.name}' eliminado.")
            except ProtectedError as e:
                messages.error(
                    request,
                    f"No se puede eliminar el campo '{pmf.field.name}' porque está en {len(e.protected_objects)} orden(es).",
                )
            return redirect("products:product_detail", product_id=product.id)

    # GET: form con instancia para autocompletar campos
    form = ProductForm(instance=product)

    measurement_fields = product.measurement_fields.select_related("field").order_by(
        "field__order"
    )
    size_variants = product.size_variants.all().order_by("size")
    used_field_ids = measurement_fields.values_list("field_id", flat=True)
    available_fields = (
        MeasurementField.objects.filter(is_active=True)
        .exclude(id__in=used_field_ids)
        .order_by("order", "name")
    )

    # Información adicional para template
    pricing_info = {}
    if requires_sizes:
        price_stats = size_variants.aggregate(
            min_additional=Min("additional_price"),
            max_additional=Max("additional_price"),
        )
        pricing_info = {
            "base_price": product.base_price,
            "min_price": product.base_price + (price_stats["min_additional"] or 0),
            "max_price": product.base_price + (price_stats["max_additional"] or 0),
            "has_variance": (price_stats["max_additional"] or 0) > 0,
        }
    else:
        pricing_info = {
            "base_price": product.base_price,
            "min_price": product.base_price,
            "max_price": product.base_price,
            "has_variance": False,
        }

    # Checklist de configuración
    configuration_checklist = []
    if requires_sizes:
        has_sizes = size_variants.exists()
        configuration_checklist.append(
            {
                "label": "Tallas configuradas",
                "status": "complete" if has_sizes else "pending",
                "message": (
                    f"{size_variants.count()} tallas"
                    if has_sizes
                    else "Agregar al menos una talla"
                ),
                "icon": "tags",
            }
        )
    if requires_measurements:
        has_fields = measurement_fields.exists()
        configuration_checklist.append(
            {
                "label": "Campos de medida",
                "status": "complete" if has_fields else "pending",
                "message": (
                    f"{measurement_fields.count()} campos"
                    if has_fields
                    else "Agregar al menos un campo"
                ),
                "icon": "rulers",
            }
        )
    if product.requires_team:
        has_team = product.owner_team is not None
        configuration_checklist.append(
            {
                "label": "Equipo propietario",
                "status": "complete" if has_team else "pending",
                "message": product.owner_team.name if has_team else "Asignar equipo",
                "icon": "people",
            }
        )

    context = {
        "product": product,
        "form": form,
        "size_variants": size_variants,
        "measurement_fields": measurement_fields,
        "available_fields": available_fields,
        "pricing_info": pricing_info,
        "configuration_checklist": configuration_checklist,
        "requires_sizes": requires_sizes,
        "requires_measurements": requires_measurements,
        "requires_design": requires_design,
        "requires_team": product.requires_team,
        "is_configured": product.is_configured,
    }

    return render(request, "products/product_detail.html", context)

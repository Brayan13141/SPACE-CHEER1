from django.contrib import messages
from django.shortcuts import render

# Create your views here.
from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from products.models import Product
from products.forms import ProductForm
from .product_templates import PRODUCT_TEMPLATES
from products.models import ProductSizeVariant
from measures.models import MeasurementField
from products.models import ProductMeasurementField


@login_required
def product_list(request):
    products = Product.objects.order_by("name")

    return render(
        request,
        "products/product_list.html",
        {"products": products},
    )


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


@login_required
@permission_required("products.add_product", raise_exception=True)
def product_create(request):

    template_key = request.GET.get("template")
    template = PRODUCT_TEMPLATES.get(template_key)

    initial_data = {}

    if template:
        initial_data = template.get("defaults", {})

    if request.method == "POST":

        form = ProductForm(
            request.POST,
            request.FILES,
            template_key=template_key,
            initial=initial_data,  # 🔥 IMPORTANTE
        )

        if form.is_valid():

            product = form.save(commit=False)

            # seguridad backend
            if template:
                defaults = template["defaults"]

                product.product_type = defaults["product_type"]
                product.usage_type = defaults["usage_type"]
                product.scope = defaults["scope"]
                product.size_strategy = defaults["size_strategy"]

            product.save()

            return redirect("products:product_configure", product_id=product.id)

    else:

        form = ProductForm(
            initial=initial_data,
            template_key=template_key,  # 🔥 faltaba esto
        )

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


@login_required
@permission_required("products.change_product", raise_exception=True)
def product_configure(request, product_id):

    product = get_object_or_404(Product, pk=product_id)

    if product.size_strategy == "STANDARD":
        return redirect("products:product_sizes", product_id=product.id)

    if product.size_strategy == "MEASUREMENTS":
        return redirect("products:product_measurements", product_id=product.id)

    return redirect("products:list_products")


@login_required
@permission_required("products.change_product", raise_exception=True)
def product_update(request, product_id):
    product = get_object_or_404(Product, pk=product_id)

    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            form.save()
            return redirect("products:list_products")
    else:
        form = ProductForm(instance=product)

    return render(
        request,
        "products/product_form.html",
        {"form": form, "title": "Editar producto"},
    )


@login_required
@permission_required("products.delete_product", raise_exception=True)
def product_delete(request, product_id):
    product = get_object_or_404(Product, pk=product_id)

    if request.method == "POST":
        product.is_active = False
        product.save(update_fields=["is_active"])
        return redirect("products:list_products")

    return render(
        request,
        "products/product_confirm_delete.html",
        {"product": product},
    )


@login_required
@permission_required("products.change_product", raise_exception=True)
def product_sizes(request, product_id):

    product = get_object_or_404(Product, pk=product_id)

    if product.size_strategy != "STANDARD":
        return redirect("products:list_products")

    sizes = product.size_variants.all()

    return render(
        request,
        "products/product_sizes.html",
        {
            "product": product,
            "sizes": sizes,
        },
    )


@login_required
@permission_required("products.change_product", raise_exception=True)
def product_size_add(request, product_id):

    product = get_object_or_404(Product, pk=product_id)

    if request.method == "POST":

        size = request.POST.get("size")
        price = request.POST.get("additional_price") or 0

        if ProductSizeVariant.objects.filter(product=product, size=size).exists():

            messages.error(request, "Esta talla ya existe")
            return redirect("products:product_sizes", product.id)

        ProductSizeVariant.objects.create(
            product=product,
            size=size,
            additional_price=price,
        )
        product.update_configuration_status()

        return redirect("products:product_sizes", product_id=product.id)

    return render(
        request,
        "products/product_size_form.html",
        {"product": product},
    )


@login_required
@permission_required("products.change_product", raise_exception=True)
def product_measurements(request, product_id):

    product = get_object_or_404(Product, pk=product_id)

    if product.size_strategy != "MEASUREMENTS":
        return redirect("products:list_products")

    fields = product.measurement_fields.select_related("field")

    return render(
        request,
        "products/product_measurements.html",
        {
            "product": product,
            "fields": fields,
        },
    )


@login_required
@permission_required("products.change_product", raise_exception=True)
def product_measurement_add(request, product_id):

    product = get_object_or_404(Product, pk=product_id)

    fields = MeasurementField.objects.all()

    if request.method == "POST":

        field_id = request.POST.get("field")
        required = bool(request.POST.get("required"))

        # verificar duplicado
        if ProductMeasurementField.objects.filter(
            product=product, field_id=field_id
        ).exists():

            messages.error(
                request, "Este campo de medida ya está agregado a este producto"
            )

            return redirect("products:product_measurements", product.id)

        ProductMeasurementField.objects.create(
            product=product,
            field_id=field_id,
            required=required,
        )
        product.update_configuration_status()
        return redirect(
            "products:product_measurements",
            product_id=product.id,
        )

    return render(
        request,
        "products/product_measurement_form.html",
        {
            "product": product,
            "fields": fields,
        },
    )

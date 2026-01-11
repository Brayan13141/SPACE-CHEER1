from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from accounts.decorators import full_profile_required, role_required
from .models import MeasurementField
from .forms import MeasurementFieldForm


@full_profile_required
@role_required("ADMIN")
def manage_measurement_fields(request):

    fields = MeasurementField.objects.filter(is_active=True).order_by("order", "name")

    # ================= POST =================
    if request.method == "POST":

        # -------- CREAR --------
        if "crear_medida" in request.POST:
            form = MeasurementFieldForm(request.POST)

            if form.is_valid():
                field = form.save()
                messages.success(
                    request,
                    f"Campo '{field.name}' creado correctamente.",
                )
            else:
                messages.error(request, "Error al crear el campo.")

            return redirect("manage_measurement_fields")

        # -------- EDITAR --------
        elif "editar_medida" in request.POST:
            field_id = request.POST.get("field_id")
            field = get_object_or_404(MeasurementField, id=field_id)

            form = MeasurementFieldForm(request.POST, instance=field)

            if form.is_valid():
                field = form.save()
                messages.success(
                    request,
                    f"Campo '{field.name}' actualizado correctamente.",
                )
            else:
                messages.error(request, "Error al actualizar el campo.")

            return redirect("manage_measurement_fields")

        # -------- DESACTIVAR --------
        elif "eliminar_medida" in request.POST:
            field_id = request.POST.get("field_id")
            field = get_object_or_404(MeasurementField, id=field_id)

            field.is_active = False
            field.save()

            messages.success(
                request,
                f"Campo '{field.name}' desactivado correctamente.",
            )

            return redirect("manage_measurement_fields")

    # ================= GET =================
    fields_with_forms = [
        {
            "field": field,
            "form": MeasurementFieldForm(instance=field),
        }
        for field in fields
    ]

    return render(
        request,
        "measures/manage_fields.html",
        {
            "fields_with_forms": fields_with_forms,
            "form_crear": MeasurementFieldForm(),
        },
    )

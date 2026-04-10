from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from urllib3 import request
from accounts.decorators import role_required
from .models import MeasurementField
from .forms import MeasurementFieldForm
import traceback  # Para mostrar detalles del error


@role_required("ADMIN")
def manage_measurement_fields(request):

    fields = MeasurementField.objects.order_by("order", "name")

    # ================= POST =================
    if request.method == "POST":

        # -------- CREAR --------
        if "crear_medida" in request.POST:
            try:
                form = MeasurementFieldForm(request.POST)
                if form.is_valid():
                    field = form.save()
                    messages.success(
                        request, f"Campo '{field.name}' creado correctamente."
                    )
                else:
                    messages.error(
                        request, f"Error al crear el campo: {form.errors.as_json()}"
                    )
            except Exception as e:
                messages.error(
                    request,
                    f"Ocurrió un error inesperado al crear el campo: {str(e)}\n{traceback.format_exc()}",
                )
            return redirect("measures:manage_measurement_fields")

        # -------- EDITAR --------
        elif "editar_medida" in request.POST:
            field_id = request.POST.get("field_id")
            field = get_object_or_404(MeasurementField, id=field_id)
            try:
                form = MeasurementFieldForm(request.POST, instance=field)
                if form.is_valid():
                    field = form.save()
                    messages.success(
                        request, f"Campo '{field.name}' actualizado correctamente."
                    )
                else:
                    messages.error(
                        request,
                        f"Error al actualizar el campo: {form.errors.as_json()}",
                    )
            except Exception as e:
                messages.error(
                    request,
                    f"Ocurrió un error inesperado al actualizar el campo: {str(e)}\n{traceback.format_exc()}",
                )
            return redirect("measures:manage_measurement_fields")

        # -------- DESACTIVAR --------
        elif "eliminar_medida" in request.POST:
            field_id = request.POST.get("field_id")
            field = get_object_or_404(MeasurementField, id=field_id)
            try:
                field.is_active = False
                field.save()
                messages.success(
                    request, f"Campo '{field.name}' desactivado correctamente."
                )
            except Exception as e:
                messages.error(
                    request,
                    f"Ocurrió un error inesperado al desactivar el campo: {str(e)}\n{traceback.format_exc()}",
                )
            return redirect("measures:manage_measurement_fields")
            # -------- HABILITAR --------
        elif "habilitar_medida" in request.POST:
            field_id = request.POST.get("field_id")
            field = get_object_or_404(MeasurementField, id=field_id)
            try:
                field.is_active = True
                field.save()
                messages.success(
                    request, f"Campo '{field.name}' habilitado correctamente."
                )
            except Exception as e:
                messages.error(
                    request,
                    f"Ocurrió un error inesperado al habilitar el campo: {str(e)}\n{traceback.format_exc()}",
                )
            return redirect("measures:manage_measurement_fields")

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

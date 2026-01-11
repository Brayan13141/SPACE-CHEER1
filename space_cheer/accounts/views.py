# accounts/views.py

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .forms import UserProfilingForm, CurpForm


def profile_setup_view(request):
    """
    Primer paso: completar datos del usuario (sin CURP).
    """
    user = request.user

    if user.roles.filter(requires_curp=True).exists() and not user.curp:
        return redirect("accounts:curp_verification")

    # Si ya tiene un rol y nombre, saltar este paso
    if user.roles.exists() and user.first_name:
        return redirect("dashboard")

    if request.method == "POST":
        form = UserProfilingForm(request.POST, instance=user)

        if form.is_valid():
            user_instance = form.save(commit=False)
            selected_role = form.cleaned_data["role"]

            # Guardamos el usuario
            user_instance.save()

            # Guardamos el rol ManyToMany
            user_instance.roles.set([selected_role])

            # Si su rol exige CURP → ir al segundo formulario
            if selected_role.requires_curp:
                return redirect("accounts:curp_verification")

            # Si NO requiere CURP, ir al dashboard directamente
            return redirect("dashboard")

    else:
        form = UserProfilingForm(instance=user)

    return render(
        request,
        "account/profile_setup.html",
        {"form": form, "title": "Completa tu Perfil"},
    )


@login_required
def curp_verification(request):
    user = request.user

    # Si ya tiene CURP, no tiene sentido volver aquí
    if user.curp:
        return redirect("dashboard")

    if request.method == "POST":
        form = CurpForm(request.POST, instance=user)

        if form.is_valid():
            form.save()
            return redirect("dashboard")

    else:
        form = CurpForm(instance=user)

    return render(request, "account/curp_verification.html", {"form": form})

# accounts/views.py

from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.decorators import login_required
from .models import UserAddress
from .forms import UserAddressForm, UserProfilingForm, CurpForm


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


@login_required
def address_list(request):
    addresses = request.user.addresses.all()
    return render(
        request, "account/addresses/list_address.html", {"addresses": addresses}
    )


@login_required
def address_create(request):
    if request.method == "POST":
        form = UserAddressForm(request.POST)
        if form.is_valid():
            address = form.save(commit=False)
            address.user = request.user
            address.save()
            return redirect("accounts:list_address")
    else:
        form = UserAddressForm()

    return render(request, "account/addresses/form.html", {"form": form})


@login_required
def address_update(request, pk):
    address = get_object_or_404(UserAddress, pk=pk, user=request.user)

    if request.method == "POST":
        form = UserAddressForm(request.POST, instance=address)
        if form.is_valid():
            form.save()
            return redirect("accounts:list_address")
    else:
        form = UserAddressForm(instance=address)

    return render(request, "account/addresses/form.html", {"form": form})


@login_required
def address_delete(request, pk):
    address = get_object_or_404(UserAddress, pk=pk, user=request.user)

    if request.method == "POST":
        address.delete()
        return redirect("accounts:list_address")

    return render(
        request, "account/addresses/confirm_delete.html", {"address": address}
    )

# accounts/views.py

from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.decorators import login_required
from accounts.models import UserAddress
from accounts.forms import UserAddressForm, UserProfilingForm, CurpForm


@login_required
def profile_setup_view(request):
    user = request.user
    if request.method == "POST":
        form = UserProfilingForm(request.POST, instance=user)

        if form.is_valid():
            user_instance = form.save(commit=False)
            selected_role = form.cleaned_data["role"]

            user_instance.save()
            user_instance.roles.set([selected_role])
            user_instance.profile_completed = True
            user_instance.save()
            if selected_role.requires_curp:
                return redirect("accounts:curp_verification")

            return redirect("dashboard")

    else:
        form = UserProfilingForm(instance=user)

    return render(
        request,
        "account/profile_setup.html",
        {"form": form},
    )


@login_required
def curp_verification(request):
    user = request.user

    if user.curp:
        if user.roles.filter(name="GUARDIAN").exists():
            return redirect("guardian:dashboard")
        else:
            return redirect("core:dashboard")

    if request.method == "POST":
        form = CurpForm(request.POST, instance=user)

        if form.is_valid():
            form.save()
            if user.roles.filter(name="GUARDIAN").exists():
                return redirect("guardian:dashboard")
            else:
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

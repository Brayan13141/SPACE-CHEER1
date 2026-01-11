# accounts/decorators.py

from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages


def full_profile_required(view):
    # Si es una Class-Based View
    if hasattr(view, "dispatch"):
        original_dispatch = view.dispatch

        @wraps(original_dispatch)
        def new_dispatch(self, request, *args, **kwargs):
            user = request.user

            if not user.is_authenticated:
                return redirect("account_login")

            if user.is_superuser:
                return original_dispatch(self, request, *args, **kwargs)

            if not user.roles.exists():
                return redirect("accounts:profile_setup")

            role = user.roles.first()
            if role and role.requires_curp and not user.curp:
                return redirect("accounts:curp_verification")

            return original_dispatch(self, request, *args, **kwargs)

        view.dispatch = new_dispatch
        return view

    # Si es una Function-Based View
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        user = request.user

        if not user.is_authenticated:
            return redirect("account_login")

        if user.is_superuser:
            return view(request, *args, **kwargs)

        if not user.roles.exists():
            return redirect("accounts:profile_setup")

        role = user.roles.first()
        if role and role.requires_curp and not user.curp:
            return redirect("accounts:curp_verification")

        return view(request, *args, **kwargs)

    return wrapper


def role_required(*allowed_roles):

    def decorator(view):
        if hasattr(view, "dispatch"):
            # Es una class-based view
            original_dispatch = view.dispatch

            @wraps(original_dispatch)
            def new_dispatch(self, request, *args, **kwargs):

                user = request.user

                if not user.is_authenticated:
                    messages.error(request, "Debes iniciar sesión.")
                    return redirect("account_login")

                if user.is_superuser:
                    return original_dispatch(self, request, *args, **kwargs)

                user_roles = set(user.roles.values_list("name", flat=True))

                if not user_roles.intersection(allowed_roles):
                    messages.error(
                        request, "No tienes permisos para acceder a esta sección."
                    )
                    return redirect("dashboard")

                return original_dispatch(self, request, *args, **kwargs)

            view.dispatch = new_dispatch
            return view

        else:
            # Es una función normal
            @wraps(view)
            def wrapped(request, *args, **kwargs):
                user = request.user

                if not user.is_authenticated:
                    messages.error(request, "Debes iniciar sesión.")
                    return redirect("account_login")

                if user.is_superuser:
                    return view(request, *args, **kwargs)

                user_roles = set(user.roles.values_list("name", flat=True))

                if not user_roles.intersection(allowed_roles):
                    messages.error(
                        request, "No tienes permisos para acceder a esta sección."
                    )
                    return redirect("dashboard")

                return view(request, *args, **kwargs)

            return wrapped

    return decorator

# accounts/decorators.py

import logging
from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from accounts.utils.redirect_flow import get_user_redirect_flow

logger = logging.getLogger(__name__)


def role_required(*allowed_roles):
    """
    Verifica que el usuario tenga alguno de los roles permitidos.
    También respeta el flujo global (onboarding, CURP, etc).
    """

    def decorator(view_func):

        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            user = request.user

            # 1. Autenticación
            if not user.is_authenticated:
                messages.error(request, "Debes iniciar sesión.")
                return redirect("account_login")

            if not user.profile_completed:
                return redirect(get_user_redirect_flow(user))

            # 2. Superuser bypass
            if user.is_superuser:
                return view_func(request, *args, **kwargs)

            # 4. Validación de roles
            user_roles = set(user.roles.values_list("name", flat=True))
            allowed_roles_set = set(allowed_roles)

            if user_roles.intersection(allowed_roles_set):
                return view_func(request, *args, **kwargs)

            # 5. Acceso denegado
            messages.error(request, "No tienes permisos para acceder a esta sección.")

            logger.warning(
                "Acceso denegado: user=%s roles=%s requiere=%s",
                user.username,
                list(user_roles),
                list(allowed_roles_set),
            )

            return redirect(get_user_redirect_flow(user))

        return wrapper

    return decorator

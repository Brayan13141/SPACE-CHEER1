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


def minor_access_required(min_level="READ_ONLY"):
    """
    Bloquea a atletas menores que no cumplan el nivel mínimo de acceso.
    Si el usuario no es menor, lo deja pasar sin revisar nada.

    Uso:
        @minor_access_required(min_level="ACTIVE")
        def my_view(request): ...
    """
    _LEVEL_ORDER = {
        "BLOCKED": 0,
        "READ_ONLY": 1,
        "ACTIVE": 2,
    }

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            from custody.services.minor_access_service import MinorAccessService

            user = request.user
            if not user.is_authenticated:
                return redirect("account_login")

            level = MinorAccessService.get_access_level(user)

            if level is None:
                # No es menor — dejar pasar
                return view_func(request, *args, **kwargs)

            if _LEVEL_ORDER.get(level, 0) < _LEVEL_ORDER.get(min_level, 0):
                return redirect("guardian:minor_blocked")

            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator

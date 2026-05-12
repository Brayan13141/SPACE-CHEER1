from django.conf import settings
from ipware import get_client_ip


class AdminIPWhitelistMiddleware:
    """
    Bloquea acceso al panel de admin para IPs no autorizadas.
    Solo actúa cuando ADMIN_ALLOWED_IPS está configurado en el entorno.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        admin_url = "/" + settings.ADMIN_URL.lstrip("/")
        allowed_ips = [ip for ip in getattr(settings, "ADMIN_ALLOWED_IPS", []) if ip]

        if request.path.startswith(admin_url) and allowed_ips:
            ip, _ = get_client_ip(request)
            if ip not in allowed_ips:
                from django.http import HttpResponseForbidden
                return HttpResponseForbidden()

        return self.get_response(request)


class PermissionsPolicyMiddleware:
    """Agrega el header Permissions-Policy usando PERMISSIONS_POLICY de settings."""

    def __init__(self, get_response):
        self.get_response = get_response
        policy = getattr(settings, "PERMISSIONS_POLICY", {})
        parts = []
        for feature, origins in policy.items():
            if not origins:
                parts.append(f"{feature}=()")
            else:
                formatted = " ".join(f'"{o}"' for o in origins)
                parts.append(f"{feature}=({formatted})")
        self._header_value = ", ".join(parts)

    def __call__(self, request):
        response = self.get_response(request)
        if self._header_value:
            response["Permissions-Policy"] = self._header_value
        return response

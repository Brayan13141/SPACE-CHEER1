# accounts/services/pii_audit_service.py
"""
Servicio centralizado para auditoría de acceso a datos PII.

Uso desde cualquier view que accede a datos sensibles:

    from accounts.services.pii_audit_service import PiiAuditService

    @full_profile_required
    @role_required("HEADCOACH")
    def view_athlete_medical(request, athlete_id):
        athlete = get_object_or_404(User, id=athlete_id)

        # SIEMPRE loggear antes de mostrar datos sensibles
        PiiAuditService.log(
            request=request,
            target_user=athlete,
            access_type="VIEW_MEDICAL",
            field_accessed="medical_info",
        )
        ...

Reglas:
- NUNCA loggear en bulk_create (ya lo maneja BulkImportService)
- El log no debe fallar silenciosamente — usa try/except para no
  romper la view si el log falla, pero sí loggea el error
- Un acceso fallido (403, 404) NO se loggea — solo accesos exitosos
"""

import logging
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)
User = get_user_model()


class PiiAuditService:
    """
    Escribe registros en PiiAccessLog.
    Diseñado para ser llamado desde views, nunca desde templates.
    """

    @staticmethod
    def log(
        *,
        request,
        target_user,
        access_type: str,
        field_accessed: str = "",
        notes: str = "",
    ) -> None:
        """
        Registra un acceso a datos PII.

        Parámetros:
            request: HttpRequest — para extraer IP y usuario actual
            target_user: User — dueño de los datos accedidos
            access_type: str — código del tipo de acceso (ver PiiAccessLog.ACCESS_TYPES)
            field_accessed: str — campo específico (ej: "curp", "birth_date")
            notes: str — contexto adicional opcional

        No lanza excepciones: el log no debe romper el flujo de la view.
        """
        from accounts.models import PiiAccessLog

        try:
            # Extraer IP del request (considera proxies con X-Forwarded-For)
            ip = PiiAuditService._get_client_ip(request)

            PiiAccessLog.objects.create(
                accessed_by=request.user if request.user.is_authenticated else None,
                target_user=target_user,
                access_type=access_type,
                field_accessed=field_accessed,
                ip_address=ip,
                notes=notes,
            )

        except Exception as e:
            # El log falló — no romper la view, pero sí alertar
            logger.error(
                "PiiAuditService.log falló: %s | accessed_by=%s target=%s type=%s",
                e,
                getattr(request, "user", "unknown"),
                target_user,
                access_type,
                exc_info=True,
            )

    @staticmethod
    def log_bulk_import(*, request, count: int, notes: str = "") -> None:
        """
        Log específico para importaciones masivas CSV.
        No tiene target_user individual porque son múltiples usuarios.
        """
        from accounts.models import PiiAccessLog

        try:
            ip = PiiAuditService._get_client_ip(request)
            PiiAccessLog.objects.create(
                accessed_by=request.user if request.user.is_authenticated else None,
                target_user=None,
                access_type="BULK_IMPORT",
                field_accessed="csv_import",
                ip_address=ip,
                notes=f"Importados: {count} usuarios. {notes}",
            )
        except Exception as e:
            logger.error("PiiAuditService.log_bulk_import falló: %s", e)

    @staticmethod
    def get_access_history(target_user, limit: int = 50):
        """
        Retorna el historial de accesos a los datos de un usuario.
        Útil para mostrar en el dashboard de privacidad.
        """
        from accounts.models import PiiAccessLog

        return (
            PiiAccessLog.objects.filter(target_user=target_user)
            .select_related("accessed_by")
            .order_by("-timestamp")[:limit]
        )

    @staticmethod
    def _get_client_ip(request) -> str:
        """
        Extrae la IP real del cliente, considerando proxies inversos.
        En producción con Nginx/AWS, la IP real viene en X-Forwarded-For.
        """
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            # X-Forwarded-For puede tener múltiples IPs: "client, proxy1, proxy2"
            return x_forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "")

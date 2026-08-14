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
from ipware import get_client_ip

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

    # Ventana de coalescencia de log_many(). Dos vistas del mismo grid por el
    # mismo usuario dentro de esta ventana dejan UN registro, no dos.
    # Súbela para reducir aún más el volumen; bájala a 0 para registrar cada
    # carga de página por separado.
    DEDUPE_WINDOW_MINUTES = 30

    @staticmethod
    def log_many(
        *,
        request,
        target_users,
        access_type: str,
        field_accessed: str = "",
        notes: str = "",
        dedupe_window_minutes: int = None,
    ) -> int:
        """Registra un acceso a varios sujetos a la vez, sin duplicar.

        ¿Por qué existe? El grid de medidas muestra el roster completo: el
        panel admin llegaba a insertar un registro por atleta POR ITEM en cada
        carga de página, y un refresco duplicaba todo. Una bitácora que crece
        así deja de servir para investigar, que es justo para lo que la exige
        la LFPDPPP.

        Qué hace: colapsa los sujetos repetidos dentro de la misma llamada y
        omite los que ya tienen un registro idéntico (mismo actor, sujeto,
        tipo, campo Y notas) dentro de la ventana de deduplicación.

        `notes` entra en la clave a propósito: identifica la superficie desde
        la que se miró (panel admin, grid, piso de producción). Sin él, ver a
        un menor desde producción justo después de verlo desde el panel
        dejaría un solo registro y la bitácora perdería desde dónde se accedió,
        que es la mitad de lo que hay que poder demostrar.

        Esto NO contradice la regla de "nunca loggear en bulk_create" del
        encabezado: esa regla es sobre no emitir un registro por usuario
        durante una importación masiva. Aquí las filas son las mismas que
        escribiría log() una por una; solo cambia que van en una sentencia.

        Devuelve cuántos registros se escribieron. No lanza excepciones.
        """
        from django.utils import timezone
        from datetime import timedelta

        from accounts.models import PiiAccessLog

        try:
            if dedupe_window_minutes is None:
                dedupe_window_minutes = PiiAuditService.DEDUPE_WINDOW_MINUTES

            # Colapsa repetidos y descarta los que no tienen pk todavía.
            unique_targets = {}
            for target_user in target_users:
                if target_user is not None and target_user.pk is not None:
                    unique_targets.setdefault(target_user.pk, target_user)

            if not unique_targets:
                return 0

            actor = request.user if request.user.is_authenticated else None

            if actor is not None and dedupe_window_minutes > 0:
                cutoff = timezone.now() - timedelta(minutes=dedupe_window_minutes)
                already_logged = set(
                    PiiAccessLog.objects.filter(
                        accessed_by=actor,
                        target_user_id__in=unique_targets.keys(),
                        access_type=access_type,
                        field_accessed=field_accessed,
                        notes=notes,
                        timestamp__gte=cutoff,
                    ).values_list("target_user_id", flat=True)
                )
                for target_id in already_logged:
                    unique_targets.pop(target_id, None)

            if not unique_targets:
                return 0

            ip = PiiAuditService._get_client_ip(request)
            PiiAccessLog.objects.bulk_create(
                [
                    PiiAccessLog(
                        accessed_by=actor,
                        target_user=target_user,
                        access_type=access_type,
                        field_accessed=field_accessed,
                        ip_address=ip,
                        notes=notes,
                    )
                    for target_user in unique_targets.values()
                ]
            )
            return len(unique_targets)

        except Exception as e:
            logger.error(
                "PiiAuditService.log_many falló: %s | accessed_by=%s type=%s",
                e,
                getattr(request, "user", "unknown"),
                access_type,
                exc_info=True,
            )
            return 0

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
        ip, _ = get_client_ip(request)
        return ip or "0.0.0.0"

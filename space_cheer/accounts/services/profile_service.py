# accounts/services/profile_service.py
"""
Servicio para gestión del perfil del usuario.

Responsabilidades:
- Validación y guardado de foto de perfil (con magic byte check)
- Edición de datos básicos del perfil
- Creación automática de NotificationPreferences y PrivacySettings
- Desactivación de cuenta (soft delete)

La validación de imágenes usa python-magic (ya tienes en el stack por orders).
Si no está instalado: pip install python-magic
"""

import logging
import os

from django.core.exceptions import ValidationError
from django.db import transaction
from django.contrib.auth import get_user_model
from django.utils import timezone

logger = logging.getLogger(__name__)
User = get_user_model()

# Tipos MIME permitidos para foto de perfil
ALLOWED_PHOTO_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_PHOTO_SIZE_MB = 5
MAX_PHOTO_SIZE_BYTES = MAX_PHOTO_SIZE_MB * 1024 * 1024


class ProfileService:
    """
    Gestiona la edición y configuración del perfil de usuario.
    """

    # =========================================================================
    # FOTO DE PERFIL
    # =========================================================================

    @staticmethod
    def upload_profile_photo(*, user, photo_file) -> User:
        """
        Valida y guarda la foto de perfil del usuario.

        Validaciones:
        1. Tamaño máximo (5MB)
        2. Magic bytes — no confiar en Content-Type del cliente
        3. Tipo MIME permitido (JPEG, PNG, WEBP)

        Retorna el usuario actualizado.
        Lanza ValidationError si la validación falla.
        """
        # --- Validar tamaño ---
        if photo_file.size > MAX_PHOTO_SIZE_BYTES:
            raise ValidationError(
                f"La foto no puede superar {MAX_PHOTO_SIZE_MB}MB. "
                f"Tu archivo pesa {photo_file.size / (1024*1024):.1f}MB."
            )

        # --- Validar magic bytes (tipo real del archivo) ---
        mime_type = ProfileService._detect_mime_type(photo_file)

        if mime_type not in ALLOWED_PHOTO_TYPES:
            raise ValidationError(
                f"Tipo de archivo no permitido: {mime_type}. "
                f"Solo se aceptan: JPEG, PNG, WEBP."
            )

        # --- Eliminar foto anterior si existe ---
        if user.foto_perfil:
            ProfileService._delete_old_photo(user)

        # --- Guardar nueva foto ---
        user.foto_perfil = photo_file
        user.save(update_fields=["foto_perfil"])

        logger.info("Foto de perfil actualizada para usuario %s", user.username)
        return user

    @staticmethod
    def delete_profile_photo(*, user) -> User:
        """Elimina la foto de perfil del usuario."""
        if not user.foto_perfil:
            return user

        ProfileService._delete_old_photo(user)
        user.foto_perfil = None
        user.save(update_fields=["foto_perfil"])
        return user

    # =========================================================================
    # EDICIÓN DE PERFIL
    # =========================================================================

    @staticmethod
    @transaction.atomic
    def update_profile(
        *,
        user,
        first_name: str = None,
        last_name: str = None,
        phone: str = None,
        birth_date=None,
        gender: str = None,
    ) -> User:
        """
        Actualiza los datos básicos del perfil.
        Solo actualiza los campos que se pasan (None = no cambiar).

        Aplica las mismas validaciones que User.clean():
        - Teléfono: 10 dígitos numéricos únicos
        - Email: no se puede cambiar aquí (flujo separado via allauth)
        """
        updated_fields = []

        if first_name is not None:
            user.first_name = first_name.strip()
            updated_fields.append("first_name")

        if last_name is not None:
            user.last_name = last_name.strip()
            updated_fields.append("last_name")

        if phone is not None:
            # Normalizar teléfono
            normalized = phone.strip().replace(" ", "").replace("-", "")
            if normalized and not normalized.isdigit():
                raise ValidationError(
                    {"phone": "El teléfono solo debe contener números."}
                )
            if normalized and len(normalized) != 10:
                raise ValidationError({"phone": "El teléfono debe tener 10 dígitos."})
            # Verificar unicidad excluyendo el usuario actual
            if (
                normalized
                and User.objects.filter(phone=normalized).exclude(pk=user.pk).exists()
            ):
                raise ValidationError({"phone": "Este número ya está registrado."})
            user.phone = normalized or None
            updated_fields.append("phone")

        if birth_date is not None:
            user.birth_date = birth_date
            updated_fields.append("birth_date")

        if gender is not None:
            if gender not in ("H", "M", ""):
                raise ValidationError({"gender": "Género inválido."})
            user.gender = gender or None
            updated_fields.append("gender")

        if updated_fields:
            user.save(update_fields=updated_fields)
            logger.info(
                "Perfil actualizado para %s: %s",
                user.username,
                updated_fields,
            )

        return user

    # =========================================================================
    # DESACTIVACIÓN DE CUENTA
    # =========================================================================

    @staticmethod
    @transaction.atomic
    def deactivate_account(*, user, deactivated_by, reason: str = "") -> User:
        """
        Desactiva una cuenta (soft delete).

        No elimina el usuario — pone is_active=False.
        Esto preserva la integridad referencial con órdenes, medidas, etc.

        Solo ADMIN o el propio usuario pueden desactivar.
        """
        # Validar permisos
        is_self = deactivated_by == user
        is_admin = (
            deactivated_by.is_superuser
            or deactivated_by.roles.filter(name="ADMIN").exists()
        )

        if not (is_self or is_admin):
            from django.core.exceptions import PermissionDenied

            raise PermissionDenied("No tienes permisos para desactivar esta cuenta.")

        user.is_active = False
        user.save(update_fields=["is_active"])

        logger.warning(
            "Cuenta desactivada: %s | por: %s | razón: %s",
            user.username,
            deactivated_by.username,
            reason or "sin razón especificada",
        )

        return user

    # =========================================================================
    # CREACIÓN DE PREFERENCIAS (llamado en onboarding)
    # =========================================================================

    @staticmethod
    def ensure_preferences_exist(user) -> None:
        """
        Crea NotificationPreferences y PrivacySettings si no existen.
        Idempotente — seguro llamar múltiples veces.

        Llamar al final de profile_setup_view cuando el usuario completa onboarding.
        """
        from accounts.models import NotificationPreferences, PrivacySettings
        from custody.services.minor_service import MinorAthleteService

        NotificationPreferences.objects.get_or_create(user=user)

        # Menores tienen PRIVATE por default, adultos TEAM
        default_visibility = "PRIVATE" if MinorAthleteService.is_minor(user) else "TEAM"

        privacy, created = PrivacySettings.objects.get_or_create(
            user=user,
            defaults={"profile_visibility": default_visibility},
        )

        if created:
            logger.info(
                "Preferencias creadas para %s (visibility=%s)",
                user.username,
                default_visibility,
            )

    # =========================================================================
    # HELPERS PRIVADOS
    # =========================================================================

    @staticmethod
    def _detect_mime_type(file) -> str:
        """
        Detecta el tipo MIME real usando magic bytes.
        Lee los primeros 2048 bytes y restaura el cursor.
        """
        try:
            import magic

            file.seek(0)
            header = file.read(2048)
            file.seek(0)
            return magic.from_buffer(header, mime=True)

        except ImportError:
            # python-magic no está instalado
            # Fallback: usar Content-Type del cliente (menos seguro)
            logger.warning(
                "python-magic no está instalado. "
                "Usando Content-Type del cliente para validación de foto. "
                "Instalar: pip install python-magic"
            )
            content_type = getattr(file, "content_type", "application/octet-stream")
            return content_type

    @staticmethod
    def _delete_old_photo(user) -> None:
        """Elimina el archivo físico de la foto anterior."""
        if not user.foto_perfil:
            return
        try:
            storage = user.foto_perfil.storage
            path = user.foto_perfil.name
            if storage.exists(path):
                storage.delete(path)
        except Exception as e:
            # No interrumpir el flujo si falla el borrado
            logger.warning(
                "No se pudo eliminar foto anterior de %s: %s",
                user.username,
                e,
            )

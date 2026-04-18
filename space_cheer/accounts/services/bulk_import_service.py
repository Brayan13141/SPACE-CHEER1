# accounts/services/bulk_import_service.py
"""
Servicio de importación masiva de atletas desde CSV.

Formato esperado del CSV:
    first_name,last_name,email,phone,birth_date,gender
    Ana,García,ana@gmail.com,5512345678,2005-03-15,M
    Carlos,López,,5598765432,,H

Reglas:
- first_name y last_name son obligatorios
- email es único en el sistema (se valida fila por fila)
- phone: 10 dígitos, opcional
- birth_date: YYYY-MM-DD, opcional
- gender: H o M, opcional
- Si el email ya existe y la fila es válida → actualizar ownership (no crear duplicado)
- Errores por fila NO abortan las demás filas
- Máximo 200 filas por importación

Uso:
    result = BulkImportService.import_from_csv(
        csv_file=request.FILES["csv"],
        imported_by=request.user,
    )
    # result.success_count, result.error_rows, result.created_users
"""

import csv
import io
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from django.contrib.auth import get_user_model
from django.db import transaction
from django.core.exceptions import ValidationError

from accounts.services.ownership_service import OwnershipService

logger = logging.getLogger(__name__)
User = get_user_model()

MAX_ROWS = 200
REQUIRED_FIELDS = {"first_name", "last_name"}
VALID_HEADERS = {"first_name", "last_name", "email", "phone", "birth_date", "gender"}


@dataclass
class ImportRowError:
    row_number: int
    data: dict
    error: str


@dataclass
class ImportResult:
    success_count: int = 0
    skipped_count: int = 0
    created_users: list = field(default_factory=list)
    error_rows: List[ImportRowError] = field(default_factory=list)

    @property
    def total_processed(self):
        return self.success_count + self.skipped_count + len(self.error_rows)

    @property
    def has_errors(self):
        return len(self.error_rows) > 0


class BulkImportService:
    """
    Importa atletas desde un archivo CSV.
    Cada fila se procesa en su propia transacción para aislar errores.
    """

    @staticmethod
    def import_from_csv(*, csv_file, imported_by) -> ImportResult:
        """
        Procesa el archivo CSV e importa los atletas.

        Parámetros:
            csv_file: archivo subido (InMemoryUploadedFile o similar)
            imported_by: User — coach que hace la importación

        Retorna ImportResult con el resumen de la operación.
        """
        result = ImportResult()

        # --- Leer y validar el archivo ---
        try:
            content = csv_file.read().decode(
                "utf-8-sig"
            )  # utf-8-sig maneja BOM de Excel
        except UnicodeDecodeError:
            try:
                csv_file.seek(0)
                content = csv_file.read().decode("latin-1")
            except Exception:
                raise ValidationError(
                    "No se pudo leer el archivo. Asegúrate de que esté en UTF-8 o Latin-1."
                )

        reader = csv.DictReader(io.StringIO(content))

        # --- Validar headers ---
        headers = set(reader.fieldnames or [])
        missing = REQUIRED_FIELDS - headers
        if missing:
            raise ValidationError(
                f"El CSV debe tener las columnas: {', '.join(REQUIRED_FIELDS)}. "
                f"Faltan: {', '.join(missing)}"
            )

        # --- Procesar filas ---
        rows = list(reader)

        if len(rows) > MAX_ROWS:
            raise ValidationError(
                f"El CSV tiene {len(rows)} filas. El máximo por importación es {MAX_ROWS}."
            )

        for i, row in enumerate(rows, start=2):  # start=2 porque fila 1 es header
            row_result = BulkImportService._process_row(
                row=row,
                row_number=i,
                imported_by=imported_by,
            )

            if isinstance(row_result, ImportRowError):
                result.error_rows.append(row_result)
            elif row_result == "skipped":
                result.skipped_count += 1
            else:
                result.success_count += 1
                result.created_users.append(row_result)

        logger.info(
            "Importación CSV completada por %s: %d creados, %d omitidos, %d errores",
            imported_by.username,
            result.success_count,
            result.skipped_count,
            len(result.error_rows),
        )

        return result

    @staticmethod
    def _process_row(*, row: dict, row_number: int, imported_by) -> object:
        """
        Procesa una fila del CSV.

        Retorna:
        - User creado si exitoso
        - "skipped" si el usuario ya existe y ya tiene ownership con este coach
        - ImportRowError si hay un error
        """
        from accounts.models import Role, UserOwnership

        try:
            # --- Limpiar datos ---
            first_name = row.get("first_name", "").strip()
            last_name = row.get("last_name", "").strip()
            email = row.get("email", "").strip().lower()
            phone = (
                row.get("phone", "").strip().replace("-", "").replace(" ", "") or None
            )
            birth_date_str = row.get("birth_date", "").strip()
            gender = row.get("gender", "").strip().upper()

            # --- Validaciones básicas ---
            if not first_name:
                raise ValidationError("first_name es requerido.")
            if not last_name:
                raise ValidationError("last_name es requerido.")

            if phone and (not phone.isdigit() or len(phone) != 10):
                raise ValidationError(
                    f"Teléfono inválido: '{phone}'. Debe ser 10 dígitos."
                )

            birth_date = None
            if birth_date_str:
                try:
                    birth_date = datetime.strptime(birth_date_str, "%Y-%m-%d").date()
                except ValueError:
                    raise ValidationError(
                        f"Fecha inválida: '{birth_date_str}'. Formato esperado: YYYY-MM-DD."
                    )

            if gender and gender not in ("H", "M"):
                raise ValidationError(f"Género inválido: '{gender}'. Use H o M.")

            with transaction.atomic():
                # --- Buscar usuario existente por email ---
                existing_user = None
                if email:
                    existing_user = User.objects.filter(email=email).first()

                if existing_user:
                    # Verificar si ya tiene ownership con este coach
                    already_owned = UserOwnership.objects.filter(
                        owner=imported_by,
                        user=existing_user,
                        is_active=True,
                    ).exists()

                    if already_owned:
                        return "skipped"

                    # Agregar a ownership sin crear duplicado de usuario
                    OwnershipService.add_to_ownership(
                        owner=imported_by,
                        user=existing_user,
                        activated_by=imported_by,
                    )
                    return existing_user

                # --- Crear nuevo usuario ---
                # Generar username único
                username = BulkImportService._generate_username(first_name, last_name)

                # Validar email único si se proporcionó
                if email and User.objects.filter(email=email).exists():
                    raise ValidationError(f"Email '{email}' ya registrado.")

                # Validar phone único si se proporcionó
                if phone and User.objects.filter(phone=phone).exists():
                    raise ValidationError(f"Teléfono '{phone}' ya registrado.")

                new_user = User.objects.create_user(
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    email=email
                    or f"{username}@pending.local",  # email placeholder si no hay
                    phone=phone,
                    birth_date=birth_date,
                    gender=gender or None,
                    password="$Temporal123!",  # Cambiar en primer login
                    profile_completed=False,
                    is_active=True,
                )

                # Asignar rol ATLETA — la señal crea AthleteProfile
                atleta_role, _ = Role.objects.get_or_create(name="ATHLETE")
                new_user.roles.add(atleta_role)

                # Crear ownership
                OwnershipService.add_to_ownership(
                    owner=imported_by,
                    user=new_user,
                    activated_by=imported_by,
                )

                return new_user

        except ValidationError as e:
            error_msg = " | ".join(e.messages) if hasattr(e, "messages") else str(e)
            return ImportRowError(row_number=row_number, data=row, error=error_msg)

        except Exception as e:
            logger.exception("Error inesperado en fila %d: %s", row_number, e)
            return ImportRowError(
                row_number=row_number,
                data=row,
                error=f"Error interno: {str(e)}",
            )

    @staticmethod
    def _generate_username(first_name: str, last_name: str) -> str:
        """Genera username único basado en nombre."""
        base = f"{first_name[:3]}{last_name[:4]}".lower().replace(" ", "")
        # Remover caracteres especiales
        base = "".join(c for c in base if c.isalnum())
        if not base:
            base = "ATHLETE"

        username = base
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base}{counter}"
            counter += 1
        return username

    @staticmethod
    def get_csv_template() -> str:
        """
        Retorna el contenido del CSV de plantilla para descarga.
        Los coaches pueden descargar esto, llenarlo y subir.
        """
        return (
            "first_name,last_name,email,phone,birth_date,gender\n"
            "Ana,García,ana@ejemplo.com,5512345678,2005-03-15,M\n"
            "Carlos,López,carlos@ejemplo.com,5598765432,2007-08-20,H\n"
        )

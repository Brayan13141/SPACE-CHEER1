"""
Migración de datos: cifra los valores PII ya existentes en la DB.

Usa raw SQL para evitar el problema de campos históricos en apps.get_model().
Solo cifra filas que aún no tienen un token Fernet (no empiezan con 'gAAAAA').
"""

import hashlib
import hmac

from django.conf import settings
from django.db import migrations


def _fernet():
    from cryptography.fernet import Fernet, MultiFernet
    return MultiFernet([
        Fernet(k if isinstance(k, bytes) else k.encode())
        for k in settings.FERNET_KEYS
    ])


def _curp_hmac(curp: str) -> str:
    return hmac.new(
        settings.SECRET_KEY.encode(),
        curp.upper().encode(),
        hashlib.sha256,
    ).hexdigest()


def encrypt_existing_pii(apps, schema_editor):
    fernet = _fernet()

    with schema_editor.connection.cursor() as cursor:
        # ── CURPs ────────────────────────────────────────────────────
        cursor.execute(
            "SELECT id, curp FROM accounts_user WHERE curp IS NOT NULL AND curp != ''"
        )
        for user_id, curp in cursor.fetchall():
            if curp.startswith('gAAAAA'):
                continue  # ya cifrado
            encrypted = fernet.encrypt(curp.encode()).decode()
            curp_hash = _curp_hmac(curp)
            cursor.execute(
                "UPDATE accounts_user SET curp = %s, curp_hash = %s WHERE id = %s",
                [encrypted, curp_hash, user_id],
            )

        # ── Direcciones ──────────────────────────────────────────────
        cursor.execute(
            "SELECT id, address, city, zip_code FROM accounts_useraddress"
        )
        for addr_id, address, city, zip_code in cursor.fetchall():
            updates = {}
            if address and not address.startswith('gAAAAA'):
                updates['address'] = fernet.encrypt(address.encode()).decode()
            if city and not city.startswith('gAAAAA'):
                updates['city'] = fernet.encrypt(city.encode()).decode()
            if zip_code and not zip_code.startswith('gAAAAA'):
                updates['zip_code'] = fernet.encrypt(zip_code.encode()).decode()
            if updates:
                set_clause = ', '.join(f"{k} = %s" for k in updates)
                cursor.execute(
                    f"UPDATE accounts_useraddress SET {set_clause} WHERE id = %s",
                    [*updates.values(), addr_id],
                )


def decrypt_existing_pii(apps, schema_editor):
    """Reverse: descifra los datos (para revertir la migración)."""
    fernet = _fernet()

    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "SELECT id, curp FROM accounts_user WHERE curp IS NOT NULL AND curp != ''"
        )
        for user_id, curp in cursor.fetchall():
            if not curp.startswith('gAAAAA'):
                continue
            try:
                plaintext = fernet.decrypt(curp.encode()).decode()
                cursor.execute(
                    "UPDATE accounts_user SET curp = %s, curp_hash = NULL WHERE id = %s",
                    [plaintext, user_id],
                )
            except Exception:
                pass

        cursor.execute(
            "SELECT id, address, city, zip_code FROM accounts_useraddress"
        )
        for addr_id, address, city, zip_code in cursor.fetchall():
            updates = {}
            for field, value in [('address', address), ('city', city), ('zip_code', zip_code)]:
                if value and value.startswith('gAAAAA'):
                    try:
                        updates[field] = fernet.decrypt(value.encode()).decode()
                    except Exception:
                        pass
            if updates:
                set_clause = ', '.join(f"{k} = %s" for k in updates)
                cursor.execute(
                    f"UPDATE accounts_useraddress SET {set_clause} WHERE id = %s",
                    [*updates.values(), addr_id],
                )


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0007_encrypt_pii_fields'),
    ]

    operations = [
        migrations.RunPython(encrypt_existing_pii, reverse_code=decrypt_existing_pii),
    ]

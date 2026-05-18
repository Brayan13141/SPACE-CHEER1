import hashlib
import hmac

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


def _fernet() -> MultiFernet:
    return MultiFernet([
        Fernet(k if isinstance(k, bytes) else k.encode())
        for k in settings.FERNET_KEYS
    ])


def curp_hmac(curp: str) -> str:
    """Deterministic HMAC-SHA256 of a normalized CURP string. Used for unique constraint."""
    return hmac.new(
        settings.SECRET_KEY.encode(),
        curp.upper().encode(),
        hashlib.sha256,
    ).hexdigest()


class EncryptedCharField(models.TextField):
    """
    Stores Fernet-encrypted ciphertext in a TEXT DB column.
    Encryption/decryption is transparent to Python code.

    Caveats:
    - max_length validates plaintext, not ciphertext (no DB-level varchar).
    - unique=True is NOT supported — use a companion hash field instead.
    - Not filterable by value at the DB level.
    """

    def __init__(self, *args, max_length=None, **kwargs):
        self._plaintext_max_length = max_length
        kwargs.pop('max_length', None)
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        path = 'accounts.fields.EncryptedCharField'
        if self._plaintext_max_length is not None:
            kwargs['max_length'] = self._plaintext_max_length
        return name, path, args, kwargs

    def from_db_value(self, value, expression, connection):
        if not value:
            return value
        try:
            return _fernet().decrypt(value.encode()).decode()
        except (InvalidToken, Exception):
            return value  # graceful during key rotation

    def to_python(self, value):
        return value

    def get_prep_value(self, value):
        if not value:
            return value
        return _fernet().encrypt(str(value).encode()).decode()

    def validate(self, value, model_instance):
        super().validate(value, model_instance)
        if self._plaintext_max_length and value and len(value) > self._plaintext_max_length:
            raise ValidationError(
                f'Asegúrate de que este valor tenga como máximo '
                f'{self._plaintext_max_length} caracteres (tiene {len(value)}).'
            )

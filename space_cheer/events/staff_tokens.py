"""Tokens firmados para el enlace de la organización y el gafete.

El token es `pk.nonce` firmado con SECRET_KEY. Se puede reconstruir desde la base
(para reimprimir el gafete o volver a copiar el enlace), nadie lo falsifica sin
la clave, y se anula rotando o vaciando el nonce de la fila.
"""

import secrets

from django.core import signing

INVITE_SALT = 'events.staff.invite'
BADGE_SALT = 'events.staff.badge'


def new_nonce() -> str:
    return secrets.token_urlsafe(16)


def make_token(pk: int, nonce: str, salt: str) -> str:
    return signing.Signer(salt=salt).sign(f'{pk}.{nonce}')


def parse_token(token: str, salt: str):
    """(pk, nonce) si la firma es válida; None en cualquier otro caso."""
    try:
        value = signing.Signer(salt=salt).unsign(token)
        pk, nonce = value.split('.', 1)
        return int(pk), nonce
    except (signing.BadSignature, ValueError):
        return None

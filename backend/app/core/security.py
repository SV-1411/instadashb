"""Encryption-at-rest helpers (rule 5: secrets encrypted, never logged).

``EncryptedString`` is a SQLAlchemy ``TypeDecorator`` that transparently encrypts
on write and decrypts on read using Fernet (AES-128-CBC + HMAC). The plaintext
never touches the DB and the key only comes from ``FERNET_KEY``.
"""

from __future__ import annotations

from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import String, TypeDecorator

from app.config import get_settings


@lru_cache
def _fernet() -> Fernet:
    """Build the Fernet cipher from the configured key (cached per process)."""
    key = get_settings().fernet_key.get_secret_value()
    if not key:
        raise RuntimeError(
            "FERNET_KEY is not set. Generate one with: "
            'python -c "from cryptography.fernet import Fernet; '
            'print(Fernet.generate_key().decode())"'
        )
    return Fernet(key.encode())


def encrypt_secret(plaintext: str) -> str:
    """Encrypt a plaintext secret into a URL-safe token string."""
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_secret(token: str) -> str:
    """Decrypt a token produced by :func:`encrypt_secret`."""
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as exc:  # pragma: no cover - defensive
        raise ValueError("Could not decrypt secret (wrong or rotated FERNET_KEY).") from exc


class EncryptedString(TypeDecorator[str]):
    """A String column whose value is encrypted at rest with Fernet."""

    impl = String
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect: object) -> str | None:
        if value is None:
            return None
        return encrypt_secret(value)

    def process_result_value(self, value: str | None, dialect: object) -> str | None:
        if value is None:
            return None
        return decrypt_secret(value)

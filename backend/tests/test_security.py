"""Encryption-at-rest unit tests (no DB needed)."""

from __future__ import annotations

import pytest
from app.core.security import decrypt_secret, encrypt_secret


def test_encrypt_decrypt_roundtrip() -> None:
    plaintext = "EAAB-meta-long-lived-token-xyz"
    token = encrypt_secret(plaintext)
    assert token != plaintext
    assert plaintext not in token
    assert decrypt_secret(token) == plaintext


def test_encrypt_is_nondeterministic() -> None:
    # Fernet embeds a timestamp+IV, so two encryptions differ (defends pattern leaks).
    assert encrypt_secret("same") != encrypt_secret("same")


def test_decrypt_rejects_garbage() -> None:
    with pytest.raises(ValueError):
        decrypt_secret("not-a-valid-token")

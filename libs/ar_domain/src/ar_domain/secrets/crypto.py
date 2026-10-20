"""AES-256-GCM envelope encryption. Spec: docs/03-specs/03-secrets-credentials.md §2."""

import os

import orjson
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from ar_common.errors import ValidationFailedError

_NONCE = 12
_DEK = 32


def parse_keyring(raw: str) -> dict[str, bytes]:
    """Parse ``AR_DB_ENCRYPTION_KEYS`` (JSON object of id to base64 key)."""
    if raw.strip() == "":
        return {}
    loaded = orjson.loads(raw)
    if not isinstance(loaded, dict):
        raise ValidationFailedError("encryption key ring must be a JSON object")
    ring: dict[str, bytes] = {}
    for key, value in loaded.items():
        blob = _b64(str(value))
        if len(blob) != _DEK:
            raise ValidationFailedError(f"encryption key {key} must be 32 bytes")
        ring[str(key)] = blob
    return ring


def encrypt_envelope(plaintext: bytes, kek: bytes, *, aad: bytes) -> tuple[bytes, bytes, bytes]:
    """Return ``(wrapped_dek, nonce, ciphertext)``.

    ``wrapped_dek`` is ``wrap_nonce || AES-GCM(KEK, DEK)``.
    """
    dek = os.urandom(_DEK)
    nonce = os.urandom(_NONCE)
    ciphertext = AESGCM(dek).encrypt(nonce, plaintext, aad)
    wrap_nonce = os.urandom(_NONCE)
    wrapped = wrap_nonce + AESGCM(kek).encrypt(wrap_nonce, dek, aad)
    return wrapped, nonce, ciphertext


def decrypt_envelope(
    *,
    wrapped_dek: bytes,
    nonce: bytes,
    ciphertext: bytes,
    kek: bytes,
    aad: bytes,
) -> bytes:
    """Decrypt a payload whose DEK was wrapped with ``kek``."""
    wrap_nonce, wrapped = wrapped_dek[:_NONCE], wrapped_dek[_NONCE:]
    dek = AESGCM(kek).decrypt(wrap_nonce, wrapped, aad)
    return AESGCM(dek).decrypt(nonce, ciphertext, aad)


def seal(key: bytes, plaintext: bytes) -> bytes:
    """Encrypt a short blob (session tokens) with AES-256-GCM."""
    nonce = os.urandom(_NONCE)
    return nonce + AESGCM(key).encrypt(nonce, plaintext, None)


def open_sealed(key: bytes, blob: bytes) -> bytes:
    """Decrypt a blob produced by :func:`seal`."""
    nonce, ciphertext = blob[:_NONCE], blob[_NONCE:]
    return AESGCM(key).decrypt(nonce, ciphertext, None)


def _b64(value: str) -> bytes:
    import base64  # noqa: PLC0415

    padding = "=" * (-len(value) % 4)
    return base64.b64decode(value + padding)

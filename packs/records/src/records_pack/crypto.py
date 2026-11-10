"""Ed25519 manifests and AES-GCM envelopes. Spec: docs/03-specs/21-records-governance.md §1."""

from __future__ import annotations

import base64
import hashlib
import os
from typing import TYPE_CHECKING

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
    load_pem_private_key,
    load_pem_public_key,
)
from pydantic import JsonValue

from ar_common.jcs import canonical_json

if TYPE_CHECKING:
    from typing import Any


def load_private(pem: str) -> Ed25519PrivateKey:
    """Load an Ed25519 private key from PEM."""
    key = load_pem_private_key(pem.encode(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise TypeError("evidence signing key must be Ed25519")
    return key


def signing_material(store: Any) -> tuple[str, Ed25519PrivateKey]:
    """Process signing key. An empty env var generates a dev key for this process."""
    cached = bucket_key(store)
    if cached is not None:
        return cached
    pem = os.environ.get("AR_EVIDENCE_SIGNING_KEY", "").strip()
    key_id = os.environ.get("AR_EVIDENCE_SIGNING_KEY_ID", "").strip() or "evidence-k1"
    key = load_private(pem) if pem else Ed25519PrivateKey.generate()
    store.records["_signing"] = {"key_id": key_id, "key": key}
    return key_id, key


def bucket_key(store: Any) -> tuple[str, Ed25519PrivateKey] | None:
    root = getattr(store, "records", None)
    if not isinstance(root, dict):
        return None
    saved = root.get("_signing")
    if not isinstance(saved, dict):
        return None
    key = saved.get("key")
    key_id = saved.get("key_id")
    if isinstance(key, Ed25519PrivateKey) and isinstance(key_id, str):
        return key_id, key
    return None


def sign_manifest(key: Ed25519PrivateKey, body: dict[str, JsonValue]) -> tuple[str, str]:
    """Return base64 signature and hex SHA-256 of the JCS body."""
    raw = canonical_json(body)
    digest = hashlib.sha256(raw).hexdigest()
    signature = base64.b64encode(key.sign(raw)).decode("ascii")
    return signature, digest


def verify_manifest(public_pem: str, body: dict[str, JsonValue], signature: str) -> bool:
    """True when the signature matches the JCS body."""
    key = load_pem_public_key(public_pem.encode())
    if not isinstance(key, Ed25519PublicKey):
        return False
    try:
        key.verify(base64.b64decode(signature), canonical_json(body))
    except InvalidSignature, ValueError:
        return False
    return True


def public_pem(key: Ed25519PrivateKey) -> str:
    return key.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo).decode()


def private_pem(key: Ed25519PrivateKey) -> str:
    return key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()).decode()


def _kek(key: Ed25519PrivateKey) -> bytes:
    seed = key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"ar-run-record-dek").derive(
        seed
    )


def seal_blob(key: Ed25519PrivateKey, plaintext: bytes) -> dict[str, str]:
    """AES-256-GCM with a DEK wrapped by HKDF of the Ed25519 seed."""
    dek = os.urandom(32)
    nonce = os.urandom(12)
    wrapped_nonce = os.urandom(12)
    ciphertext = AESGCM(dek).encrypt(nonce, plaintext, None)
    wrapped = AESGCM(_kek(key)).encrypt(wrapped_nonce, dek, None)
    return {
        "wrapped_dek": base64.b64encode(wrapped).decode("ascii"),
        "wrapped_nonce": base64.b64encode(wrapped_nonce).decode("ascii"),
        "nonce": base64.b64encode(nonce).decode("ascii"),
        "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
    }


def open_blob(key: Ed25519PrivateKey, envelope: dict[str, str]) -> bytes:
    dek = AESGCM(_kek(key)).decrypt(
        base64.b64decode(envelope["wrapped_nonce"]),
        base64.b64decode(envelope["wrapped_dek"]),
        None,
    )
    return AESGCM(dek).decrypt(
        base64.b64decode(envelope["nonce"]), base64.b64decode(envelope["ciphertext"]), None
    )

"""Fill local secrets in .env when they are still placeholders. Spec: local-dev bootstrap."""

import base64
import secrets
from pathlib import Path

import orjson
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / ".env"


def _ensure(text: str, key: str, value: str) -> str:
    prefix = f"{key}="
    lines = text.splitlines()
    replaced = False
    for index, line in enumerate(lines):
        if line.startswith(prefix):
            current = line.split("=", 1)[1].strip()
            if current in {"", "change-me", "generate"}:
                lines[index] = f"{key}={value}"
            replaced = True
            break
    if not replaced:
        lines.append(f"{key}={value}")
    return "\n".join(lines) + "\n"


def encryption_keyring() -> str:
    """JSON object ``{"k1": "<standard base64 of 32 bytes>"}`` for ``AR_DB_ENCRYPTION_KEYS``."""
    key = base64.b64encode(secrets.token_bytes(32)).decode()
    return orjson.dumps({"k1": key}).decode()


def session_key() -> str:
    """Standard base64 of 32 bytes. URL-safe tokens fail ``b64decode``."""
    return base64.b64encode(secrets.token_bytes(32)).decode()


def main() -> None:
    private = Ed25519PrivateKey.generate()
    private_pem = private.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    public = (
        private.public_key()
        .public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    text = ENV.read_text(encoding="utf-8") if ENV.exists() else ""
    text = _ensure(text, "AR_SESSION_ENCRYPTION_KEY", session_key())
    text = _ensure(text, "AR_CURSOR_SECRET", secrets.token_urlsafe(32))
    text = _ensure(text, "AR_DB_ENCRYPTION_KEYS", "'" + encryption_keyring() + "'")
    text = _ensure(text, "AR_DB_ENCRYPTION_ACTIVE_KEY", "k1")
    text = _ensure(text, "AR_TOKEN_CACHE_KEY", session_key())
    text = _ensure(text, "AR_INTERNAL_JWT_PRIVATE_KEY", private_pem.replace("\n", "\\n"))
    text = _ensure(text, "AR_INTERNAL_JWT_JWKS", base64.b64encode(public.encode()).decode())
    ENV.write_text(text, encoding="utf-8")
    print(f"wrote dev keys to {ENV}")


if __name__ == "__main__":
    main()

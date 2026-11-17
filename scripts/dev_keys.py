"""Fill local secrets in .env when they are still placeholders. Spec: local-dev bootstrap."""

import base64
import secrets
import shlex
from pathlib import Path

import orjson
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from ar_common.internal_jwt import public_jwk

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


def shell_value(value: str) -> str:
    """Single-quote a value so sourcing ``.env`` does not split on spaces."""
    return "'" + value.replace("'", "'\"'\"'") + "'"


def session_key() -> str:
    """Standard base64 of 32 bytes. URL-safe tokens fail ``b64decode``."""
    return base64.b64encode(secrets.token_bytes(32)).decode()


def quote_json_settings(text: str) -> str:
    """Preserve legacy JSON keys while making them safe for Honcho and shell loading."""
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if not line.startswith(("AR_DB_ENCRYPTION_KEYS=", "AR_INTERNAL_JWT_JWKS=")):
            continue
        key, raw = line.split("=", 1)
        if raw.startswith("{"):
            orjson.loads(raw)
            lines[index] = f"{key}={shell_value(raw)}"
    return "\n".join(lines) + "\n"


def ensure_jwks(text: str) -> str:
    """Derive the public JWKS from the retained private key, repairing legacy PEM-base64."""
    values = {}
    for line in text.splitlines():
        if line.startswith("AR_INTERNAL_JWT_") and "=" in line:
            key, value = line.split("=", 1)
            parsed = shlex.split(value)
            values[key] = parsed[0] if parsed else ""
    private = serialization.load_pem_private_key(
        values["AR_INTERNAL_JWT_PRIVATE_KEY"].replace("\\n", "\n").encode(), password=None
    )
    if not isinstance(private, Ed25519PrivateKey):
        raise TypeError("The development service key must be Ed25519")
    public = (
        private.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )
    raw = values.get("AR_INTERNAL_JWT_JWKS", "")
    try:
        document = orjson.loads(raw)
        if isinstance(document, dict) and isinstance(document.get("keys"), list):
            return text
    except orjson.JSONDecodeError:
        pass
    legacy = base64.b64encode(public.encode()).decode()
    if raw not in {"", "change-me", "generate", legacy}:
        raise ValueError("AR_INTERNAL_JWT_JWKS is invalid; the configured value was preserved")
    value = shell_value(orjson.dumps({"keys": [public_jwk(public, "dev")]}).decode())
    lines = [line for line in text.splitlines() if not line.startswith("AR_INTERNAL_JWT_JWKS=")]
    return "\n".join([*lines, f"AR_INTERNAL_JWT_JWKS={value}"]) + "\n"


def _ensure_password(text: str, key: str, value: str) -> str:
    """Replace a missing, placeholder, or role-name password. Keep a real one."""
    bad = {
        "",
        "change-me",
        "generate",
        "ar_owner",
        "ar_app",
        "ar_platform",
        "ar_readonly",
        "postgres",
        "install-time",
        "changeme",
        "password",
        "placeholder",
        "ar-install-db",
    }
    prefix = f"{key}="
    lines = text.splitlines()
    replaced = False
    for index, line in enumerate(lines):
        if line.startswith(prefix):
            current = line.split("=", 1)[1].strip().strip("'\"")
            if current.casefold() in bad:
                lines[index] = f"{key}={value}"
            replaced = True
            break
    if not replaced:
        lines.append(f"{key}={value}")
    return "\n".join(lines) + "\n"


def _install_app_password(text: str) -> str:
    """Put AR_DB_APP_PASSWORD into a passwordless or role-name database URL."""
    values: dict[str, str] = {}
    for line in text.splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, raw = line.split("=", 1)
        values[key] = raw.strip().strip("'\"")
    app = values.get("AR_DB_APP_PASSWORD", "")
    url = values.get("AR_DATABASE_URL", "")
    marker = "postgresql+asyncpg://ar_app"
    if not app or not url.startswith(marker):
        return text
    if url.startswith(marker + "@"):
        updated = marker + ":" + app + url[len(marker) :]
    elif url.startswith(marker + ":") and "@" in url:
        secret, host = url[len(marker) + 1 :].split("@", 1)
        if secret.casefold() not in {
            "",
            "ar_app",
            "ar-install-db",
            "install-time",
            "password",
            "changeme",
        }:
            return text
        updated = marker + ":" + app + "@" + host
    else:
        return text
    lines = [line for line in text.splitlines() if not line.startswith("AR_DATABASE_URL=")]
    lines.append(f"AR_DATABASE_URL={updated}")
    return "\n".join(lines) + "\n"


def main() -> None:
    private = Ed25519PrivateKey.generate()
    private_pem = private.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    text = ENV.read_text(encoding="utf-8") if ENV.exists() else ""
    text = _ensure(text, "AR_SESSION_ENCRYPTION_KEY", session_key())
    text = _ensure(text, "AR_CURSOR_SECRET", secrets.token_urlsafe(32))
    text = _ensure(text, "AR_DB_ENCRYPTION_KEYS", shell_value(encryption_keyring()))
    text = _ensure(text, "AR_DB_ENCRYPTION_ACTIVE_KEY", "k1")
    text = _ensure(text, "AR_TOKEN_CACHE_KEY", session_key())
    text = _ensure_password(text, "AR_DB_OWNER_PASSWORD", secrets.token_urlsafe(24))
    text = _ensure_password(text, "AR_DB_PLATFORM_PASSWORD", secrets.token_urlsafe(24))
    text = _ensure_password(text, "AR_DB_APP_PASSWORD", secrets.token_urlsafe(24))
    text = _ensure_password(text, "AR_DB_READONLY_PASSWORD", secrets.token_urlsafe(24))
    text = _ensure_password(text, "POSTGRES_PASSWORD", secrets.token_urlsafe(24))
    text = _install_app_password(text)
    escaped_pem = private_pem.replace("\n", "\\n")
    text = _ensure(text, "AR_INTERNAL_JWT_PRIVATE_KEY", shell_value(escaped_pem))
    text = ensure_jwks(quote_json_settings(text))
    ENV.write_text(text, encoding="utf-8")
    print(f"wrote dev keys to {ENV}")


if __name__ == "__main__":
    main()

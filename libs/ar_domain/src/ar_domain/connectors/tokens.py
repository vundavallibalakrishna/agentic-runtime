"""Cache cloud access tokens on the connection row and, when present, Valkey.

The plaintext token is sealed with the connection key before it is stored.
A second worker reads the same ciphertext instead of minting again.
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any

from ar_common.time import utcnow

if TYPE_CHECKING:
    from datetime import datetime

_PREFIX = "ar:cloud-token:"


def cached_token(store: Any, row: dict[str, object]) -> str:
    """Return a token that is still inside its expiry, or an empty string."""
    from ar_domain.tools.service_connections import _expired, _open  # noqa: PLC0415

    if not _expired(row):
        current = _open(row.get("access_token"))
        if current:
            return current
    client = getattr(store, "valkey_client", None)
    if client is None:
        return ""
    raw = _read(client, f"{_PREFIX}{row.get('id')}")
    if not raw or "\n" not in raw:
        return ""
    expires, sealed = raw.split("\n", 1)
    if _past(expires):
        return ""
    try:
        blob = bytes.fromhex(sealed)
    except ValueError:
        return ""
    token = _open(blob)
    if token:
        _write_row(row, token, expires)
    return token


def remember_token(store: Any, row: dict[str, object], token: str, expires_in: int) -> None:
    """Seal a token onto the row and mirror it when Valkey is configured."""
    from ar_domain.tools.service_connections import _seal, _store_tokens  # noqa: PLC0415

    if not token:
        return
    lifetime = max(int(expires_in), 30)
    _store_tokens(row, {"access_token": token, "expires_in": str(lifetime)})
    client = getattr(store, "valkey_client", None)
    if client is None:
        return
    expires = str(row.get("expires_at") or "")
    payload = expires + "\n" + _seal(token).hex()
    _write(client, f"{_PREFIX}{row.get('id')}", payload, lifetime)


def _write_row(row: dict[str, object], token: str, expires: str) -> None:
    from ar_domain.tools.service_connections import _seal  # noqa: PLC0415

    row["access_token"] = _seal(token)
    row["expires_at"] = expires
    row["updated_at"] = utcnow()


def _past(raw: str) -> bool:
    from datetime import datetime  # noqa: PLC0415

    try:
        stamp = datetime.fromisoformat(raw)
    except ValueError:
        return True
    if stamp.tzinfo is None:
        return True
    return stamp <= utcnow() + timedelta(seconds=30)


def _read(client: Any, key: str) -> str:
    try:
        raw = client.get(key)
    except Exception:  # noqa: BLE001 — a cache miss falls back to a new token
        return ""
    if raw is None:
        return ""
    if isinstance(raw, bytes):
        return raw.decode()
    return str(raw)


def _write(client: Any, key: str, value: str, ttl: int) -> None:
    try:
        client.set(key, value, ex=max(ttl, 30))
    except Exception:  # noqa: BLE001 — the row still holds the sealed token
        return


def expiry_stamp(seconds: int) -> datetime:
    return utcnow() + timedelta(seconds=max(seconds, 30))

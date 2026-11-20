"""Open a tenant secret that was loaded with the tenant's rows.

A tool asks for a secret by name while it runs. The rows of ``secret_refs`` are loaded
with the rest of the tenant, with the encrypted value beside each when the install keeps
values in the database. Nothing is decrypted until a tool asks, and the plaintext is
returned to that caller only.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ar_common.errors import ArError
from ar_common.settings import get_settings
from ar_domain.secrets.crypto import decrypt_envelope, parse_keyring

if TYPE_CHECKING:
    from typing import Any

BUCKET = "stored_secrets"


def open_stored_secret(store: Any, tenant_id: object, name: str) -> str | None:
    """The value of the tenant's secret called ``name``, or None when there is none.

    Only a secret that belongs to the tenant as a whole is read by name. A personal one
    (it has an owner) is not, because a tool call does not act as that person here.
    """
    rows = getattr(store, BUCKET, None)
    if not isinstance(rows, dict) or not name:
        return None
    for row in rows.values():
        if not isinstance(row, dict) or row.get("owner_user_id") is not None:
            continue
        if str(row.get("tenant_id")) != str(tenant_id) or str(row.get("name")) != name:
            continue
        try:
            return _open(row)
        except ArError, ValueError, KeyError, OSError:
            # A value that cannot be opened is a missing secret to the tool. The reason
            # is not passed on: it could say something about the key.
            return None
    return None


def _open(row: dict[str, Any]) -> str | None:
    aad = f"{row['tenant_id']}:{row['id']}".encode()
    if row.get("backend") == "vault":
        return _from_vault(str(row.get("path") or ""))
    wrapped, nonce, ciphertext = row.get("wrapped_dek"), row.get("nonce"), row.get("ciphertext")
    if not all(isinstance(item, bytes | memoryview) for item in (wrapped, nonce, ciphertext)):
        return None
    settings = get_settings()
    kek = parse_keyring(settings.db_encryption_keys.get_secret_value()).get(str(row.get("key_id")))
    if kek is None:
        return None
    try:
        plain = decrypt_envelope(
            wrapped_dek=bytes(wrapped),  # type: ignore[arg-type]
            nonce=bytes(nonce),  # type: ignore[arg-type]
            ciphertext=bytes(ciphertext),  # type: ignore[arg-type]
            kek=kek,
            aad=aad,
        )
    except Exception:  # noqa: BLE001 — a failed tag check is a missing secret, with no detail
        return None
    return plain.decode("utf-8", errors="replace")


def _from_vault(path: str) -> str | None:
    import hvac  # noqa: PLC0415

    settings = get_settings()
    client = hvac.Client(url=settings.vault_addr, token=settings.vault_token.get_secret_value())
    try:
        payload = client.secrets.kv.v2.read_secret_version(
            path=path, mount_point=settings.vault_kv_mount
        )
    except Exception:  # noqa: BLE001 — an unreachable or missing value is a missing secret
        return None
    data = payload.get("data") if isinstance(payload, dict) else None
    inner = data.get("data", data) if isinstance(data, dict) else None
    if not isinstance(inner, dict) or "value" not in inner:
        return None
    return str(inner["value"])

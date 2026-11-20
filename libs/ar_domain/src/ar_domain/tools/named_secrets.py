"""Named secrets addressed by tenant and name. Ciphertext is what gets stored."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_domain.secrets.crypto import open_sealed, seal
from ar_domain.tools.service_connections import connection_key

if TYPE_CHECKING:
    import uuid


def stage_named_secret(tenant_id: uuid.UUID, name: str, value: str) -> dict[str, Any]:
    """A secret row that is not stored until the caller commits it."""
    now = utcnow()
    return {
        "id": new_id(),
        "tenant_id": tenant_id,
        "name": name,
        "ciphertext": seal(connection_key(), value.encode()),
        "created_at": now,
        "updated_at": now,
    }


def install_named_secret(store: Any, row: dict[str, Any]) -> None:
    """Remember a row that a transaction has already committed."""
    book = _book(store)
    tenant = str(row.get("tenant_id"))
    name = str(row.get("name"))
    for key, existing in list(book.items()):
        if (
            isinstance(existing, dict)
            and str(existing.get("tenant_id")) == tenant
            and str(existing.get("name")) == name
        ):
            book.pop(key, None)
            break
    book[row.get("id")] = row


def write_named_secret(store: Any, tenant_id: uuid.UUID, name: str, value: str) -> None:
    book = _book(store)
    sealed = seal(connection_key(), value.encode())
    for row in book.values():
        if (
            isinstance(row, dict)
            and str(row.get("tenant_id")) == str(tenant_id)
            and str(row.get("name")) == name
        ):
            row["ciphertext"] = sealed
            row["updated_at"] = utcnow()
            return
    secret_id = new_id()
    book[secret_id] = {
        "id": secret_id,
        "tenant_id": tenant_id,
        "name": name,
        "ciphertext": sealed,
        "created_at": utcnow(),
        "updated_at": utcnow(),
    }


def read_named_secret(store: Any, tenant_id: object, name: str) -> str | None:
    """The value a tool asked for by name.

    A secret the product keeps for itself (a computer's token, the callback secret) is
    in the named book. A secret a person saved is in the secret store, and is looked up
    there by its name.
    """
    if not name:
        return None
    kept = _read_kept(store, tenant_id, name)
    if kept is not None:
        return kept
    from ar_domain.secrets.loaded import open_stored_secret  # noqa: PLC0415

    return open_stored_secret(store, tenant_id, name)


def _read_kept(store: Any, tenant_id: object, name: str) -> str | None:
    book = getattr(store, "named_secrets", None)
    if not isinstance(book, dict):
        return None
    direct = book.get((str(tenant_id), name))
    if isinstance(direct, bytes):
        return direct.decode("utf-8", errors="replace")
    if isinstance(direct, str):
        return direct
    for row in book.values():
        if not isinstance(row, dict):
            continue
        if str(row.get("tenant_id")) != str(tenant_id) or str(row.get("name")) != name:
            continue
        blob = row.get("ciphertext")
        if isinstance(blob, memoryview):
            blob = blob.tobytes()
        if isinstance(blob, bytes) and blob:
            try:
                return open_sealed(connection_key(), blob).decode()
            except Exception:  # noqa: BLE001 — a bad blob is a missing secret
                return None
    return None


def _book(store: Any) -> dict[Any, Any]:
    book = getattr(store, "named_secrets", None)
    if not isinstance(book, dict):
        store.named_secrets = {}
        book = store.named_secrets
    return book

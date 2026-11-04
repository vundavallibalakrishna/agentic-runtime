"""Named secrets addressed by tenant and name. Ciphertext is what gets stored."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_domain.secrets.crypto import open_sealed, seal
from ar_domain.tools.service_connections import connection_key

if TYPE_CHECKING:
    import uuid


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
    book = getattr(store, "named_secrets", None)
    if not isinstance(book, dict) or not name:
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

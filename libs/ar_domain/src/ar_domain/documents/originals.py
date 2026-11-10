"""Original upload bytes live in the object store. The row keeps the hash and the key.

A product store declares ``objects`` and uses the configured bucket. A unit-test double
that does not declare one keeps the bytes on ``store.originals`` so they are not dropped.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ar_common.errors import ArError, ErrorCode
from ar_common.offload import blocking
from ar_common.time import utcnow
from ar_domain.files.logic import object_key

if TYPE_CHECKING:
    import uuid
    from typing import Any


def store_original(
    store: Any,
    *,
    tenant_id: uuid.UUID,
    document_id: uuid.UUID,
    data: bytes,
    media_type: str,
) -> str:
    """Put ``data`` under the library key. Returns the key."""
    now = utcnow()
    key = object_key(str(tenant_id), "library", f"{now:%Y}", f"{now:%m}", str(document_id))
    content_type = media_type or "application/octet-stream"
    objects = _objects(store)
    if objects is not None:
        from ar_common.s3 import ObjectStoreError  # noqa: PLC0415

        try:
            blocking(objects.put, key, data, content_type)
        except ObjectStoreError as exc:
            raise ArError(ErrorCode.UNAVAILABLE, str(exc)) from exc
        return key
    originals = getattr(store, "originals", None)
    if not isinstance(originals, dict):
        originals = {}
        store.originals = originals
    originals[key] = bytes(data)
    return key


def read_original(store: Any, key: str) -> bytes | None:
    """Bytes stored at ``key``, or None when that object is absent."""
    if not key:
        return None
    objects = _objects(store)
    if objects is not None:
        from ar_common.s3 import ObjectStoreError  # noqa: PLC0415

        try:
            found = blocking(objects.get, key)
        except ObjectStoreError as exc:
            raise ArError(ErrorCode.UNAVAILABLE, str(exc)) from exc
        return found if isinstance(found, bytes) else None
    originals = getattr(store, "originals", None)
    if not isinstance(originals, dict):
        return None
    found = originals.get(key)
    return found if isinstance(found, bytes) else None


def _objects(store: Any) -> Any:
    current = getattr(store, "objects", None)
    if current is not None:
        return current
    if "objects" not in getattr(store, "__dict__", {}):
        return None
    from ar_domain.files.objects import object_store  # noqa: PLC0415

    return object_store(store)

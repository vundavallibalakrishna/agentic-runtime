"""Where a file's bytes live: the object store, read when a process needs them.

A file's row is in ``files`` (through the store's write-behind like every other table);
its bytes are an object under the row's ``object_key`` in the S3-compatible store the
install names (``AR_S3_ENDPOINT``, ``AR_S3_BUCKET``). A process keeps a bounded cache of
bytes it has handled and fetches the rest on demand, never every file of the tenant at
start. Spec: docs/03-specs/13-files-artifacts.md §2.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any, Protocol

from ar_common.errors import ArError, ErrorCode
from ar_common.offload import blocking

if TYPE_CHECKING:
    from collections.abc import Mapping


class ObjectStore(Protocol):
    """What the product needs from an object store. ``ar_common.s3.S3Store`` is the one."""

    def put(self, key: str, body: bytes, content_type: str) -> None: ...

    def get(self, key: str) -> bytes | None: ...

    def delete(self, key: str) -> None: ...


def object_store(store: Any) -> ObjectStore:
    """The store's object store: the configured S3 bucket unless the setup gave another."""
    current = getattr(store, "objects", None)
    if current is not None:
        return current  # type: ignore[no-any-return]
    from ar_common.s3 import S3Store  # noqa: PLC0415
    from ar_common.settings import BaseServiceSettings  # noqa: PLC0415

    built = S3Store(BaseServiceSettings())
    store.objects = built
    return built


def keep_bytes(store: Any, row: Mapping[str, object], data: bytes) -> None:
    """Put a file's bytes under its key. The wait runs off the loop; a refusal is an error."""
    from ar_common.s3 import ObjectStoreError  # noqa: PLC0415

    key = str(row.get("object_key") or "")
    if not key:
        raise ArError(ErrorCode.INTERNAL_ERROR, "The file has no object key.")
    objects = object_store(store)
    content_type = str(row.get("mime_type") or "application/octet-stream")
    try:
        blocking(objects.put, key, data, content_type)
    except ObjectStoreError as exc:
        raise ArError(ErrorCode.UNAVAILABLE, str(exc)) from exc
    blobs = getattr(store, "blobs", None)
    if isinstance(blobs, dict):
        file_id = row.get("id")
        if isinstance(file_id, uuid.UUID):
            blobs[file_id] = data


def fetch_bytes(store: Any, row: Mapping[str, object]) -> bytes | None:
    """A file's bytes from the object store, or None when it holds no such object."""
    from ar_common.s3 import ObjectStoreError  # noqa: PLC0415

    key = str(row.get("object_key") or "")
    if not key:
        return None
    try:
        found = blocking(object_store(store).get, key)
    except ObjectStoreError as exc:
        raise ArError(ErrorCode.UNAVAILABLE, str(exc)) from exc
    if found is None:
        return None
    blobs = getattr(store, "blobs", None)
    if isinstance(blobs, dict):
        file_id = row.get("id")
        if isinstance(file_id, uuid.UUID):
            blobs[file_id] = found
    return found


def drop_bytes(store: Any, row: Mapping[str, object]) -> None:
    """Remove a file's object. Used by the retention sweep, not by a person's delete."""
    from ar_common.s3 import ObjectStoreError  # noqa: PLC0415

    key = str(row.get("object_key") or "")
    if not key:
        return
    try:
        blocking(object_store(store).delete, key)
    except ObjectStoreError as exc:
        raise ArError(ErrorCode.UNAVAILABLE, str(exc)) from exc

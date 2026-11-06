"""Object stores for tests. A test's own setup registers one; the product never does."""

from __future__ import annotations


class MemoryObjectStore:
    """Holds objects in a dict: what ``ar_common.s3.S3Store`` does, without a server."""

    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}
        self.puts = 0

    def put(self, key: str, body: bytes, content_type: str) -> None:
        self.objects[key] = (bytes(body), content_type)
        self.puts += 1

    def get(self, key: str) -> bytes | None:
        found = self.objects.get(key)
        return None if found is None else found[0]

    def delete(self, key: str) -> None:
        self.objects.pop(key, None)


class RefusingObjectStore:
    """An object store that is down, for tests of what the product says then."""

    def __init__(self, endpoint: str = "http://objects.example:9000") -> None:
        self.endpoint = endpoint

    def _refuse(self, verb: str) -> None:
        from ar_common.s3 import ObjectStoreError  # noqa: PLC0415

        raise ObjectStoreError(
            f"The object store at {self.endpoint} (bucket ar-files) did not {verb} the file. "
            "Check AR_S3_ENDPOINT, AR_S3_BUCKET, AR_S3_ACCESS_KEY_ID and AR_S3_SECRET_ACCESS_KEY."
        )

    def put(self, key: str, body: bytes, content_type: str) -> None:  # noqa: ARG002
        self._refuse("store")

    def get(self, key: str) -> bytes | None:  # noqa: ARG002
        self._refuse("read")
        return None

    def delete(self, key: str) -> None:  # noqa: ARG002
        self._refuse("remove")

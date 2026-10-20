"""Secret backend protocol. Spec: docs/03-specs/03-secrets-credentials.md §2."""

from typing import Protocol


class SecretStore(Protocol):
    """Read and write secret values. Callers never log the returned plaintext."""

    async def put(self, path: str, value: bytes, *, aad: bytes) -> None:
        """Create or replace the value at ``path``."""

    async def get(self, path: str, *, aad: bytes) -> bytes:
        """Return the plaintext at ``path``."""

    async def delete(self, path: str) -> None:
        """Remove the value at ``path``."""

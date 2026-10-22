"""Knowledge connector interface used by a later milestone. Spec: connector-sdk."""

from typing import Protocol


class DocumentSource(Protocol):
    """A pack supplies documents. Retrieval itself lands with the knowledge milestone."""

    def search(self, query: str, *, limit: int = 8) -> list[dict[str, str]]:
        """Return documents with title and text. The caller wraps them as untrusted."""

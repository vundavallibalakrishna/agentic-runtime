"""Connector helpers. HTTP details live in ``ar_domain.knowledge.fetchers``."""

from typing import TYPE_CHECKING

from ar_domain.knowledge.fetchers import (
    check,
    check_access,
    fetch_bytes,
    list_acl_changes,
    list_changes,
)

if TYPE_CHECKING:
    from typing import Any


class ConfigSource:
    """One source row plus its config."""

    kind = "upload"

    def __init__(self, source: dict[str, object], store: object | None = None) -> None:
        self.source = source
        self.store = store

    def check(self) -> dict[str, object]:
        return check(self.source)

    def list_changes(
        self, cursor: dict[str, object] | None, page_size: int = 200
    ) -> dict[str, object]:
        del cursor, page_size
        return list_changes(self._row(), mode="incremental")

    def fetch(self, item: dict[str, object]) -> tuple[bytes, str]:
        merged = dict(item)
        if self.store is not None:
            merged.setdefault("store", self.store)
            merged.setdefault("tenant_id", self.source.get("tenant_id"))
        return fetch_bytes(merged)

    def list_acl_changes(self, cursor: dict[str, object] | None = None) -> list[dict[str, object]]:
        del cursor
        return list_acl_changes(self.source)

    def _row(self) -> dict[str, object]:
        row = dict(self.source)
        if self.store is not None:
            row["store"] = self.store
        return row

    def check_access(self, external_id: str, user: Any) -> bool:
        user_id = str(getattr(user, "user_id", user))
        return check_access(self.source, external_id, user_id)

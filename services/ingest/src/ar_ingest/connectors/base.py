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

    def __init__(self, source: dict[str, object]) -> None:
        self.source = source

    def check(self) -> dict[str, object]:
        return check(self.source)

    def list_changes(
        self, cursor: dict[str, object] | None, page_size: int = 200
    ) -> dict[str, object]:
        del cursor, page_size
        return list_changes(self.source, mode="incremental")

    def fetch(self, item: dict[str, object]) -> tuple[bytes, str]:
        return fetch_bytes(item)

    def list_acl_changes(self, cursor: dict[str, object] | None = None) -> list[dict[str, object]]:
        del cursor
        return list_acl_changes(self.source)

    def check_access(self, external_id: str, user: Any) -> bool:
        user_id = str(getattr(user, "user_id", user))
        return check_access(self.source, external_id, user_id)

"""Helpers for cross-tenant tests. Spec: docs/02-architecture/tenancy-isolation.md §5."""

import re
from collections.abc import Callable

ID_PATH = re.compile(r"\{[^}]*_id\}")


def paths_with_ids(openapi: dict[str, object]) -> list[str]:
    """Return OpenAPI paths that take a resource id."""
    paths = openapi.get("paths", {})
    if not isinstance(paths, dict):
        return []
    return sorted(path for path in paths if isinstance(path, str) and ID_PATH.search(path))


def fill_path(template: str, **ids: str) -> str:
    """Replace ``{name}`` placeholders."""

    def replacer(match: re.Match[str]) -> str:
        name = match.group(0)[1:-1]
        return ids.get(name, ids.get("id", "missing"))

    return re.sub(r"\{[^}]+\}", replacer, template)


Factory = Callable[[], str]

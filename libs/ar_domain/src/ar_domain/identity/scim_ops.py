"""SCIM filter and PATCH helpers. Spec: docs/03-specs/02-identity-tenancy.md §3.9."""

import re
from typing import Literal

from ar_common.errors import ValidationFailedError

FilterField = Literal["userName", "externalId", "displayName"]
_EQ = re.compile(r'^(userName|externalId|displayName) eq "(.*)"$')


def parse_eq_filter(expression: str | None) -> tuple[FilterField, str] | None:
    """Parse a single ``attr eq \"value\"`` filter. Empty means no filter."""
    if expression is None or expression.strip() == "":
        return None
    match = _EQ.fullmatch(expression.strip())
    if match is None:
        raise ValidationFailedError("unsupported SCIM filter")
    field = match.group(1)
    if field not in {"userName", "externalId", "displayName"}:
        raise ValidationFailedError("unsupported SCIM filter")
    return field, match.group(2)  # type: ignore[return-value]


def apply_user_patch(*, active: bool, operations: list[dict[str, object]]) -> bool:
    """Apply PATCH ops that toggle ``active``. Other paths are rejected."""
    current = active
    for operation in operations:
        op = str(operation.get("op", "")).lower()
        path = operation.get("path")
        value = operation.get("value")
        if op not in {"add", "replace", "remove"}:
            raise ValidationFailedError("unsupported SCIM patch op")
        if path not in {None, "active"} and not (isinstance(value, dict) and "active" in value):
            raise ValidationFailedError("unsupported SCIM patch path")
        if op == "remove":
            current = False
            continue
        if isinstance(value, dict) and "active" in value:
            current = bool(value["active"])
        elif path == "active":
            current = bool(value)
    return current


def member_ids_from_patch(operations: list[dict[str, object]]) -> tuple[list[str], list[str]]:
    """Return ``(added user ids, removed user ids)`` from group member ops."""
    added: list[str] = []
    removed: list[str] = []
    for operation in operations:
        op = str(operation.get("op", "")).lower()
        path = str(operation.get("path", "members"))
        value = operation.get("value")
        if "members" not in path:
            continue
        identifiers = _ids(value)
        if op == "remove":
            removed.extend(identifiers)
        elif op in {"add", "replace"}:
            added.extend(identifiers)
    return added, removed


def _ids(value: object) -> list[str]:
    if isinstance(value, list):
        found: list[str] = []
        for item in value:
            if isinstance(item, dict) and "value" in item:
                found.append(str(item["value"]))
            elif isinstance(item, str):
                found.append(item)
        return found
    if isinstance(value, dict) and "value" in value:
        return [str(value["value"])]
    if isinstance(value, str):
        return [value]
    return []

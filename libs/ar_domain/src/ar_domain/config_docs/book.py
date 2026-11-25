"""Schema-checked settings for a pack or an agent. Each save is a new version."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import orjson
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from ar_common.errors import NotFoundError, ValidationFailedError
from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_domain.audit.memory import remember

if TYPE_CHECKING:
    import uuid


class SettingsBook:
    def __init__(self, store: Any) -> None:
        self.store = store

    def latest(
        self, tenant_id: uuid.UUID, resource_type: str, resource_id: str
    ) -> dict[str, object]:
        rows = self._rows(tenant_id, resource_type, resource_id)
        if not rows:
            raise NotFoundError("settings not found")
        return _public(rows[-1])

    def versions(
        self, tenant_id: uuid.UUID, resource_type: str, resource_id: str
    ) -> list[dict[str, object]]:
        return [_public(row) for row in self._rows(tenant_id, resource_type, resource_id)]

    def save(  # noqa: PLR0917
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID | None,
        resource_type: str,
        resource_id: str,
        schema: dict[str, object],
        document: dict[str, object],
    ) -> dict[str, object]:
        _check(schema, document)
        rows = self._rows(tenant_id, resource_type, resource_id)
        previous_version = rows[-1].get("version") if rows else 0
        version = (previous_version if isinstance(previous_version, int) else 0) + 1
        previous = rows[-1].get("schema") if rows else None
        schema_changed = bool(rows) and previous != schema
        row = {
            "id": new_id(),
            "tenant_id": tenant_id,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "version": version,
            "schema": schema,
            "document": document,
            "created_by": user_id,
            "created_at": utcnow(),
        }
        _book(self.store)[row["id"]] = row
        remember(
            self.store,
            tenant_id=tenant_id,
            actor_id=user_id,
            action="resource_settings.updated",
            target_type="resource_settings",
            target_id=row["id"],
            detail={
                "resource_type": resource_type,
                "resource_id": resource_id,
                "version": version,
                "schema_changed": schema_changed,
            },
        )
        return _public(row)

    def _rows(
        self, tenant_id: uuid.UUID, resource_type: str, resource_id: str
    ) -> list[dict[str, object]]:
        found = [
            row
            for row in _book(self.store).values()
            if row.get("tenant_id") == tenant_id
            and row.get("resource_type") == resource_type
            and row.get("resource_id") == resource_id
        ]
        found.sort(key=_version)
        return found


def agent_settings_block(store: Any, run: dict[str, object]) -> str:
    """The latest settings document for the run's agent, for its system prompt."""
    import uuid  # noqa: PLC0415

    tenant = run.get("tenant_id")
    if not isinstance(tenant, uuid.UUID):
        return ""
    agent_id = run.get("agent_id")
    slug = ""
    agents = getattr(store, "agents", {})
    agent = agents.get(agent_id) if isinstance(agents, dict) else None
    if isinstance(agent, dict):
        slug = str(agent.get("slug") or "")
    book = SettingsBook(store)
    for resource_id in (slug, "" if agent_id is None else str(agent_id)):
        if not resource_id:
            continue
        try:
            found = book.latest(tenant, "agent", resource_id)
        except NotFoundError:
            continue
        document = found.get("document")
        if not isinstance(document, dict):
            continue
        return (
            f"Agent settings, version {found.get('version')}. "
            "These values are configuration for this agent.\n" + orjson.dumps(document).decode()
        )
    return ""


def _version(item: dict[str, object]) -> int:
    value = item.get("version")
    return value if isinstance(value, int) else 0


def _check(schema: dict[str, object], document: dict[str, object]) -> None:
    try:
        Draft202012Validator.check_schema(schema)
        errors = sorted(
            Draft202012Validator(schema).iter_errors(document), key=lambda item: item.message
        )
    except SchemaError as exc:
        raise ValidationFailedError("settings schema is not a JSON Schema") from exc
    if errors:
        raise ValidationFailedError(errors[0].message)


def _book(store: Any) -> dict[Any, dict[str, object]]:
    found = getattr(store, "resource_settings", None)
    if not isinstance(found, dict):
        found = {}
        store.resource_settings = found
    return found


def _public(row: dict[str, object]) -> dict[str, object]:
    return {
        "id": str(row.get("id")),
        "resource_type": row.get("resource_type"),
        "resource_id": row.get("resource_id"),
        "version": row.get("version"),
        "schema": row.get("schema"),
        "document": row.get("document"),
        "created_at": row.get("created_at"),
    }

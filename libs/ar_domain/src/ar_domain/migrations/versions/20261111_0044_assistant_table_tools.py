"""Publish the seeded assistant again with the chart and table tools.

Revision ID: 0044
Revises: 0043
Create Date: 2026-11-11

The assistant every tenant is seeded with could not chart a table: its version granted
neither ``general.chart`` nor the table tools, so the model scripted a chart and failed.
A published version cannot change, so each tenant whose assistant is still the seeded
version gets a new published version with those grants, and the old one is superseded.
An assistant an administrator has published since is theirs and is left alone.

Data only. Downgrade keeps the rows: a conversation may already use the new version.
"""

import uuid
from typing import TYPE_CHECKING

import orjson
import sqlalchemy as sa
from alembic import op

from ar_common.jcs import args_hash

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0044"
down_revision: str | None = "0043"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The grants as they are in this release. A migration keeps its own copy.
_GRANTS: dict[str, tuple[str, ...]] = {
    "image": ("ask",),
    "general": ("inspect_table", "query_table", "pivot_table", "export_table", "chart"),
}


def with_grants(definition: dict[str, object]) -> dict[str, object] | None:
    """The definition with the missing grants added, or None when it has them all."""
    tools = definition.get("tools")
    if not isinstance(tools, list):
        return None
    merged = orjson.loads(orjson.dumps(tools))
    held = {str(item.get("server")): item for item in merged if isinstance(item, dict)}
    changed = False
    for server, names in _GRANTS.items():
        current = held.get(server)
        if current is None:
            merged.append({"server": server, "version": "*", "include": list(names)})
            changed = True
            continue
        include = current.get("include")
        if not isinstance(include, list) or "*" in include:
            continue
        for name in names:
            if name not in include:
                include.append(name)
                changed = True
    return {**definition, "tools": merged} if changed else None


def _hash(definition: dict[str, object]) -> str:
    body = {key: value for key, value in definition.items() if key != "resolved"}
    return args_hash(body)  # type: ignore[arg-type]


def upgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT v.id, v.tenant_id, v.agent_id, v.definition, v.created_by, v.published_by "
            "FROM agents a JOIN agent_versions v ON v.id = a.published_version_id "
            "WHERE a.slug = 'assistant' AND v.state = 'published' AND v.change_note = 'seed'"
        )
    ).mappings()
    for row in list(rows):
        stored = row["definition"]
        definition = orjson.loads(stored) if isinstance(stored, str) else dict(stored)
        fresh = with_grants(definition)
        if fresh is None:
            continue
        new_id = uuid.uuid4()
        bind.execute(
            sa.text(
                "INSERT INTO agent_versions (id, tenant_id, agent_id, version, state, definition, "
                "definition_hash, change_note, created_by, published_at, published_by) "
                "SELECT :id, :tenant_id, :agent_id, COALESCE(MAX(version), 0) + 1, 'published', "
                "CAST(:definition AS jsonb), :hash, 'seed', :created_by, now(), :published_by "
                "FROM agent_versions WHERE agent_id = :agent_id"
            ),
            {
                "id": new_id,
                "tenant_id": row["tenant_id"],
                "agent_id": row["agent_id"],
                "definition": orjson.dumps(fresh).decode(),
                "hash": _hash(fresh),
                "created_by": row["created_by"],
                "published_by": row["published_by"],
            },
        )
        bind.execute(
            sa.text(
                "INSERT INTO agent_version_bindings "
                "(tenant_id, agent_version_id, kind, target_id, target_key) "
                "SELECT tenant_id, :new_id, kind, target_id, target_key "
                "FROM agent_version_bindings WHERE agent_version_id = :old_id"
            ),
            {"new_id": new_id, "old_id": row["id"]},
        )
        bind.execute(
            sa.text("UPDATE agent_versions SET state = 'superseded' WHERE id = :old_id"),
            {"old_id": row["id"]},
        )
        bind.execute(
            sa.text("UPDATE agents SET published_version_id = :new_id WHERE id = :agent_id"),
            {"new_id": new_id, "agent_id": row["agent_id"]},
        )


def downgrade() -> None:
    """Nothing to undo: the added version is ordinary data a conversation may use."""

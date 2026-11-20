"""Publish the seeded assistant again without the `session.checkpoint` grant.

Revision ID: 0053
Revises: 0052
Create Date: 2026-11-19

`session.checkpoint` was a tool that failed the first time a run called it, so the
agent loop's retry could be tried out. It is not a capability and the product no longer
ships it (OQ-148). A development or CI install seeded its assistant with a grant for
it. A published version cannot change, so a tenant whose assistant is still a version
the seed or an earlier revision of this kind published gets a new published version
without that grant, and the old one is superseded. An assistant an administrator has
published since is theirs and is left alone, and so is a grant of the whole server.

Data only. Downgrade publishes a new version with the grant back, under the change
note the version before this revision had, so the earlier revisions of this kind still
recognise it. It does not edit a published row in place. Restart API and worker
processes after the migration so they load the new published version.
"""

import uuid
from typing import TYPE_CHECKING

import orjson
import sqlalchemy as sa
from alembic import op

from ar_common.jcs import args_hash

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0053"
down_revision: str | None = "0052"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The grant this revision takes away. A migration keeps its own copy.
_SERVER = "session"
_TOOL = "checkpoint"
# Change notes of the versions the product itself published for the assistant.
_OURS = ("seed", "offline-default", "sample-and-saved-queries")
_NOTE = "without-checkpoint"


def without_grant(definition: dict[str, object]) -> dict[str, object] | None:
    """The definition without the grant, or None when it does not name the tool."""
    tools = definition.get("tools")
    if not isinstance(tools, list):
        return None
    kept: list[object] = []
    changed = False
    for item in tools:
        include = item.get("include") if isinstance(item, dict) else None
        if (
            not isinstance(item, dict)
            or item.get("server") != _SERVER
            or not isinstance(include, list)
            or _TOOL not in include
        ):
            kept.append(item)
            continue
        changed = True
        left = [name for name in include if name != _TOOL]
        if left:
            kept.append({**item, "include": left})
    return {**definition, "tools": kept} if changed else None


def with_grant(definition: dict[str, object]) -> dict[str, object]:
    """The definition with the grant back. A grant of the whole server is kept as it is."""
    tools = definition.get("tools")
    if not isinstance(tools, list):
        return definition
    merged = orjson.loads(orjson.dumps(tools))
    current = next(
        (item for item in merged if isinstance(item, dict) and item.get("server") == _SERVER),
        None,
    )
    if current is None:
        merged.insert(0, {"server": _SERVER, "version": "*", "include": [_TOOL]})
        return {**definition, "tools": merged}
    include = current.get("include")
    if isinstance(include, list) and "*" not in include and _TOOL not in include:
        include.append(_TOOL)
    return {**definition, "tools": merged}


def _hash(definition: dict[str, object]) -> str:
    """Same digest the product writes for a definition: SHA-256 of its JCS encoding."""
    return args_hash(definition)  # type: ignore[arg-type]


def _publish(bind: sa.Connection, row: sa.RowMapping, fresh: dict[str, object], note: str) -> None:
    new_id = uuid.uuid4()
    bind.execute(
        sa.text(
            "INSERT INTO agent_versions (id, tenant_id, agent_id, version, state, definition, "
            "definition_hash, change_note, created_by, published_at, published_by) "
            "SELECT :id, :tenant_id, :agent_id, COALESCE(MAX(version), 0) + 1, 'published', "
            "CAST(:definition AS jsonb), :hash, :note, :created_by, now(), :published_by "
            "FROM agent_versions WHERE agent_id = :agent_id"
        ),
        {
            "id": new_id,
            "tenant_id": row["tenant_id"],
            "agent_id": row["agent_id"],
            "definition": orjson.dumps(fresh).decode(),
            "hash": _hash(fresh),
            "note": note,
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


def _definition(row: sa.RowMapping) -> dict[str, object]:
    stored = row["definition"]
    return orjson.loads(stored) if isinstance(stored, str) else dict(stored)


def upgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT v.id, v.tenant_id, v.agent_id, v.definition, v.created_by, v.published_by "
            "FROM agents a JOIN agent_versions v ON v.id = a.published_version_id "
            "WHERE a.slug = 'assistant' AND v.state = 'published' "
            "AND v.change_note IN :ours"
        ).bindparams(sa.bindparam("ours", expanding=True)),
        {"ours": list(_OURS)},
    ).mappings()
    for row in list(rows):
        fresh = without_grant(_definition(row))
        if fresh is not None:
            _publish(bind, row, fresh, _NOTE)


def downgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT v.id, v.tenant_id, v.agent_id, v.definition, v.created_by, v.published_by, "
            "(SELECT p.change_note FROM agent_versions p WHERE p.agent_id = v.agent_id "
            " AND p.version < v.version ORDER BY p.version DESC LIMIT 1) AS earlier_note "
            "FROM agents a JOIN agent_versions v ON v.id = a.published_version_id "
            "WHERE a.slug = 'assistant' AND v.change_note = :note"
        ),
        {"note": _NOTE},
    ).mappings()
    for row in list(rows):
        earlier = str(row["earlier_note"] or "")
        note = earlier if earlier in _OURS else "seed"
        _publish(bind, row, with_grant(_definition(row)), note)

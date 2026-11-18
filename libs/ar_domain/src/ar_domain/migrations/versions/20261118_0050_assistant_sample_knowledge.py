"""Publish the seeded assistant again with sampling, saved queries and knowledge search.

Revision ID: 0050
Revises: 0049
Create Date: 2026-11-18

New tenants already receive an assistant that can draw a sample from a table, save a
query and run it again, and search knowledge. A published version cannot change, so a
tenant whose assistant is still the version a seed or an earlier revision of this kind
published gets a new published version with those grants, and the old one is
superseded. An assistant an administrator has published since is theirs and is left
alone.

Data only. Downgrade publishes a new version without those grants, under the change
note the version before this revision had, so the earlier revisions of this kind still
recognise it. It does not edit a published row in place. Restart API and worker
processes after the migration so they load the new published version.
"""

import uuid
from typing import TYPE_CHECKING

import orjson
import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0050"
down_revision: str | None = "0049"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The grants as they are in this release. A migration keeps its own copy.
_GRANTS: dict[str, tuple[str, ...]] = {
    "general": ("sample_table", "save_query", "list_saved_queries", "run_saved_query"),
    "knowledge": ("search",),
}
# Change notes of the versions the product itself published for the assistant.
_OURS = ("seed", "offline-default")
_NOTE = "sample-and-saved-queries"


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


def without_grants(definition: dict[str, object]) -> dict[str, object]:
    """The definition without the grants this revision adds. A wildcard grant is kept."""
    tools = definition.get("tools")
    if not isinstance(tools, list):
        return definition
    kept: list[object] = []
    for item in tools:
        names = _GRANTS.get(str(item.get("server"))) if isinstance(item, dict) else None
        include = item.get("include") if isinstance(item, dict) else None
        if names is None or not isinstance(include, list) or "*" in include:
            kept.append(item)
            continue
        left = [name for name in include if str(name) not in names]
        if left:
            kept.append({**item, "include": left})
    return {**definition, "tools": kept}


def _hash(definition: dict[str, object]) -> str:
    """Same digest ``agents.logic.definition_hash`` writes."""
    from ar_domain.agents.logic import definition_hash  # noqa: PLC0415

    return definition_hash(definition)


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
        fresh = with_grants(_definition(row))
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
        _publish(bind, row, without_grants(_definition(row)), note)

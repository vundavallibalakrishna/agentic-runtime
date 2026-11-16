"""Drop web tools from the seeded assistant.

Revision ID: 0046
Revises: 0045
Create Date: 2026-11-15

New tenants already receive an assistant without ``general.fetch``, ``general.http``
and ``general.search``. This revision publishes that same grant for a tenant whose
assistant is still the seeded version. An assistant an administrator has published
since is left alone.

To give the tools back, edit the assistant and add ``fetch``, ``http`` and ``search``
to the general include list.

Downgrade publishes a new version that puts those three names back. It does not
edit the published row in place. Restart API and worker processes after the
migration so they load the new published version.
"""

import uuid
from typing import TYPE_CHECKING

import orjson
import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0046"
down_revision: str | None = "0045"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_WEB = ("fetch", "http", "search")
_NOTE = "offline-default"


def _without(definition: dict[str, object]) -> dict[str, object] | None:
    tools = definition.get("tools")
    if not isinstance(tools, list):
        return None
    changed = False
    fresh: list[object] = []
    for item in tools:
        if not isinstance(item, dict) or str(item.get("server")) != "general":
            fresh.append(item)
            continue
        include = item.get("include")
        if not isinstance(include, list) or "*" in include:
            fresh.append(item)
            continue
        kept = [name for name in include if str(name) not in _WEB]
        if len(kept) != len(include):
            changed = True
            fresh.append({**item, "include": kept})
        else:
            fresh.append(item)
    if not changed:
        return None
    return {**definition, "tools": fresh}


def _with(definition: dict[str, object]) -> dict[str, object]:
    tools = definition.get("tools")
    merged: list[object] = []
    if not isinstance(tools, list):
        return definition
    for item in tools:
        if not isinstance(item, dict) or str(item.get("server")) != "general":
            merged.append(item)
            continue
        include = item.get("include")
        if not isinstance(include, list) or "*" in include:
            merged.append(item)
            continue
        names = [str(name) for name in include]
        for name in _WEB:
            if name not in names:
                names.append(name)
        merged.append({**item, "include": names})
    return {**definition, "tools": merged}


def _hash(definition: dict[str, object]) -> str:
    """Same digest ``agents.logic.definition_hash`` writes, including ``resolved``."""
    from ar_domain.agents.logic import definition_hash  # noqa: PLC0415

    return definition_hash(definition)


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
        fresh = _without(definition)
        if fresh is None:
            continue
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
                "note": _NOTE,
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
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT v.id, v.tenant_id, v.agent_id, v.definition, v.created_by, v.published_by "
            "FROM agents a JOIN agent_versions v ON v.id = a.published_version_id "
            "WHERE a.slug = 'assistant' AND v.change_note = :note"
        ),
        {"note": _NOTE},
    ).mappings()
    for row in list(rows):
        stored = row["definition"]
        definition = orjson.loads(stored) if isinstance(stored, str) else dict(stored)
        fresh = _with(definition)
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
            sa.text("UPDATE agent_versions SET state = 'superseded' WHERE id = :old_id"),
            {"old_id": row["id"]},
        )
        bind.execute(
            sa.text("UPDATE agents SET published_version_id = :new_id WHERE id = :agent_id"),
            {"new_id": new_id, "agent_id": row["agent_id"]},
        )

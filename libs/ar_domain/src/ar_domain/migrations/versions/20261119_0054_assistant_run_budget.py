"""Publish the seeded assistant again with run limits that fit multi-step work.

Revision ID: 0054
Revises: 0053
Create Date: 2026-11-19

The assistant was seeded with a run budget of 16,000 tokens, 8 model steps, 8 tool
calls, 120 seconds and a cost cap of 1,000,000 micros. Its first prompt alone is about
10,000 tokens, and a request that needed several tool calls stopped on a limit before
it could answer (OQ-149). New tenants receive 80,000 tokens, 16 steps, 16 tool calls,
600 seconds and 4,000,000 micros. A published version cannot change, so a tenant whose
assistant is still a version the seed or an earlier revision of this kind published
gets a new published version, and the old version is superseded. Each of the five
values is looked at on its own: one that is still exactly what the seed wrote becomes
the new default, and one that is anything else stays as it is. An assistant an
administrator has published since is theirs and is left alone.

Data only. Downgrade publishes a new version with the old values back, value by value,
under the change note the version before this revision had, so the earlier revisions
of this kind still recognise it. It does not edit a published row in place. Restart
API and worker processes after the migration so they load the new published version.
"""

import uuid
from typing import TYPE_CHECKING

import orjson
import sqlalchemy as sa
from alembic import op

from ar_common.jcs import args_hash

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0054"
down_revision: str | None = "0053"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# What the seed used to write and what it writes now. A migration keeps its own copy.
# The seed stores the definition with snake_case keys.
_OLD: dict[str, int] = {
    "max_steps": 8,
    "max_tokens": 16_000,
    "max_cost_micros": 1_000_000,
    "max_wall_clock_s": 120,
    "max_tool_calls": 8,
}
_NEW: dict[str, int] = {
    "max_steps": 16,
    "max_tokens": 80_000,
    "max_cost_micros": 4_000_000,
    "max_wall_clock_s": 600,
    "max_tool_calls": 16,
}
# Change notes of the versions the product itself published for the assistant.
_OURS = ("seed", "offline-default", "sample-and-saved-queries", "without-checkpoint")
_NOTE = "run-budget"


def with_budget(
    definition: dict[str, object], old: dict[str, int], new: dict[str, int]
) -> dict[str, object] | None:
    """The definition with each limit that is exactly ``old`` set to ``new``.

    A limit that holds any other value is kept. None when no limit changes.
    """
    budget = definition.get("budget")
    if not isinstance(budget, dict):
        return None
    fresh = dict(budget)
    for key, was in old.items():
        current = budget.get(key)
        if isinstance(current, bool) or not isinstance(current, int) or current != was:
            continue
        fresh[key] = new[key]
    if fresh == budget:
        return None
    return {**definition, "budget": fresh}


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
        fresh = with_budget(_definition(row), _OLD, _NEW)
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
        back = with_budget(_definition(row), _NEW, _OLD)
        if back is not None:
            _publish(bind, row, back, note)

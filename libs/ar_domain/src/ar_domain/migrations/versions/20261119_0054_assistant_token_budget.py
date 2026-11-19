"""Publish the seeded assistant again with a token limit that fits multi-step work.

Revision ID: 0054
Revises: 0053
Create Date: 2026-11-19

The assistant was seeded with a run limit of 16,000 tokens. Its first prompt alone is
about 10,000, so a request that needed several tool calls stopped on the limit before
it could answer (OQ-149). New tenants receive 80,000. A published version cannot
change, so a tenant whose assistant is still a version the seed or an earlier revision
of this kind published, and still has the old limit, gets a new published version with
the new one, and the old version is superseded. An assistant an administrator has
published since is theirs and is left alone, and so is any other value of the limit.

Data only. Downgrade publishes a new version with the old limit back, under the change
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

revision: str = "0054"
down_revision: str | None = "0053"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The limit the seed used to write and the one it writes now. A migration keeps its own
# copy. The seed stores the definition with snake_case keys.
_OLD = 16_000
_NEW = 80_000
# Change notes of the versions the product itself published for the assistant.
_OURS = ("seed", "offline-default", "sample-and-saved-queries", "without-checkpoint")
_NOTE = "token-budget"


def with_limit(definition: dict[str, object], old: int, new: int) -> dict[str, object] | None:
    """The definition with ``new`` as its token limit, or None unless the limit is ``old``."""
    budget = definition.get("budget")
    if not isinstance(budget, dict):
        return None
    current = budget.get("max_tokens")
    if isinstance(current, bool) or not isinstance(current, int) or current != old:
        return None
    return {**definition, "budget": {**budget, "max_tokens": new}}


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
        fresh = with_limit(_definition(row), _OLD, _NEW)
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
        back = with_limit(_definition(row), _NEW, _OLD)
        if back is not None:
            _publish(bind, row, back, note)

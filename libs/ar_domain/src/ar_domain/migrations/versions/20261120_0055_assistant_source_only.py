"""Publish the seeded assistant again, told to add nothing a source does not state.

Revision ID: 0055
Revises: 0054
Create Date: 2026-11-20

Asked for a matrix from a document without naming its columns, the assistant added
ratings the document does not hold, with a real model. New tenants receive instructions
that say to include only what the source states and what the person asked for, and to
add no rating, score or assessment of its own unless asked. A published version cannot
change, so a tenant whose assistant is still a version the seed or an earlier revision
of this kind published gets a new published version with that sentence added after the
one about passages that were not found, and the old version is superseded. Instructions
that do not hold that sentence, or already hold the new one, are left alone. An
assistant an administrator has published since is theirs and is left alone.

Data only. Downgrade publishes a new version without the sentence, under the change
note the version before this revision had. It does not edit a published row in place.
Restart API and worker processes after the migration so they load the new version.
"""

import uuid
from typing import TYPE_CHECKING

import orjson
import sqlalchemy as sa
from alembic import op

from ar_common.jcs import args_hash

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0055"
down_revision: str | None = "0054"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The sentence the seed now writes, and the one it follows. A migration keeps its own copy.
_AFTER = "If a tool says the passage was not found, say that and do not invent it. "
_ADDED = (
    "When you build a table, a matrix or a summary from a source, include only what the "
    "source states and what the person asked for. Do not add a rating, a score or an "
    "assessment of your own unless asked, and when asked, say that it is yours. "
)
# Change notes of the versions the product itself published for the assistant.
_OURS = (
    "seed",
    "offline-default",
    "sample-and-saved-queries",
    "without-checkpoint",
    "run-budget",
)
_NOTE = "source-only"


def with_sentence(definition: dict[str, object]) -> dict[str, object] | None:
    """The definition with the sentence added to its instructions. None when nothing changes."""
    text = definition.get("instructions")
    if not isinstance(text, str) or _ADDED in text or _AFTER not in text:
        return None
    return {**definition, "instructions": text.replace(_AFTER, _AFTER + _ADDED, 1)}


def without_sentence(definition: dict[str, object]) -> dict[str, object] | None:
    """The definition with the sentence taken out again. None when it is not there."""
    text = definition.get("instructions")
    if not isinstance(text, str) or _ADDED not in text:
        return None
    return {**definition, "instructions": text.replace(_ADDED, "", 1)}


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
        fresh = with_sentence(_definition(row))
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
        back = without_sentence(_definition(row))
        if back is not None:
            _publish(bind, row, back, note)

"""Remove model providers of kind ``fake`` and the kind itself.

Revision ID: 0065
Revises: 0064
Create Date: 2026-11-25

A provider of kind ``fake`` was a stand-in for a model: the product treated an alias that
pointed at one as not connected, and a dev install was seeded with one. The product no
longer knows the kind (M38a-T07). This revision deletes such providers with their models,
deletes the aliases whose primary model was one of those models, takes those models out of
every alias's fallback list, and narrows the kind check to the three kinds that call a
real endpoint.

An alias that pointed at a fake model is deleted, not repointed: there is nothing to point
it at. The product then says that no model is connected to the alias, which was already
true. Messages, knowledge collections and memory rows that named such a model keep their
rows; their model column is set to NULL by the foreign key.

The downgrade restores the wider check. It does not bring the deleted rows back.
"""

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0065"
down_revision: str | None = "0064"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CHECK = "ck_model_providers_kind"
_FAKE_MODELS = (
    "SELECT m.id FROM models m JOIN model_providers p ON p.id = m.provider_id WHERE p.kind = 'fake'"
)


def upgrade() -> None:
    op.execute(
        f"""
        UPDATE model_aliases a
        SET fallback_model_ids = ARRAY(
            SELECT kept FROM unnest(a.fallback_model_ids) AS kept
            WHERE kept NOT IN ({_FAKE_MODELS})
        )
        WHERE a.fallback_model_ids && ARRAY({_FAKE_MODELS})
        """  # noqa: S608 — both parts are constants in this file
    )
    op.execute(
        f"DELETE FROM model_aliases WHERE primary_model_id IN ({_FAKE_MODELS})"  # noqa: S608
    )
    op.execute("DELETE FROM model_providers WHERE kind = 'fake'")
    op.drop_constraint(op.f(_CHECK), "model_providers", type_="check")
    op.create_check_constraint(
        op.f(_CHECK), "model_providers", "kind IN ('openai_compatible','vllm','tei')"
    )


def downgrade() -> None:
    op.drop_constraint(op.f(_CHECK), "model_providers", type_="check")
    op.create_check_constraint(
        op.f(_CHECK), "model_providers", "kind IN ('openai_compatible','vllm','tei','fake')"
    )

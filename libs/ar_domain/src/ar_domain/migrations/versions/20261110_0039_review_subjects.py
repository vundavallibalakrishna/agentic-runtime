"""Widen review queue subjects to the names the product already accepts.

Revision ID: 0039
Revises: 0038
Create Date: 2026-11-10

Expand. Existing rows keep their subject. The extra names are the ones
``REVIEW_SUBJECTS`` already allowed in process memory.
"""

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0039"
down_revision: str | None = "0038"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_WIDE = (
    "subject_type IN ('artifact','file','message','evidence_item','sealed_record',"
    "'run_record','agent_card','binder','packet','pack_record')"
)
_NARROW = (
    "subject_type IN ('artifact','file','message','evidence_item',"
    "'run_record','agent_card','binder','pack_record')"
)


def upgrade() -> None:
    op.drop_constraint(op.f("ck_review_queues_subject_type"), "review_queues", type_="check")
    op.create_check_constraint("ck_review_queues_subject_type", "review_queues", _WIDE)


def downgrade() -> None:
    op.drop_constraint(op.f("ck_review_queues_subject_type"), "review_queues", type_="check")
    op.create_check_constraint("ck_review_queues_subject_type", "review_queues", _NARROW)

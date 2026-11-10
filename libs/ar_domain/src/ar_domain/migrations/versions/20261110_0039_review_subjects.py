"""Widen review queue subjects to the names the product already accepts.

Revision ID: 0039
Revises: 0038
Create Date: 2026-11-10

Expand. Existing rows keep their subject. The replacement constraint uses the
name the model convention produces, ``ck_review_queues_subject_type``.
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
_SWAP = """
DO $$
DECLARE cname text;
BEGIN
  SELECT con.conname INTO cname
  FROM pg_constraint con
  JOIN pg_class rel ON rel.oid = con.conrelid
  WHERE rel.relname = 'review_queues'
    AND con.contype = 'c'
    AND pg_get_constraintdef(con.oid) LIKE '%subject_type%'
  LIMIT 1;
  IF cname IS NOT NULL THEN
    EXECUTE format('ALTER TABLE review_queues DROP CONSTRAINT %I', cname);
  END IF;
END $$;
"""


def upgrade() -> None:
    op.execute(_SWAP)
    op.execute(
        f"ALTER TABLE review_queues ADD CONSTRAINT ck_review_queues_subject_type CHECK ({_WIDE})"
    )


def downgrade() -> None:
    op.execute(_SWAP)
    op.execute(
        f"ALTER TABLE review_queues ADD CONSTRAINT ck_review_queues_subject_type CHECK ({_NARROW})"
    )

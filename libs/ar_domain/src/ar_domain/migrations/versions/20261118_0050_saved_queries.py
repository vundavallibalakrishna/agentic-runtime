"""Saved table queries, and review queues that sign them.

Revision ID: 0050
Revises: 0049
Create Date: 2026-11-18

Expand. ``saved_queries`` holds one row per version of a named query. A version is
written once: the table is append-only, so a signed statement cannot be edited under
its sign-off. ``review_queues.subject_type`` gains ``saved_query``. Downgrade drops the
table and restores the earlier subject list for new rows; existing queues are left in
place (``NOT VALID``). Restart processes after upgrading so they load the new table.
"""

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

from ar_domain.migrations.helpers import add_append_only_trigger, enable_tenant_rls, grant_table

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0050"
down_revision: str | None = "0049"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_EARLIER = (
    "subject_type IN ('artifact','file','message','evidence_item','sealed_record',"
    "'run_record','agent_card','binder','packet','pack_record')"
)
_WIDE = (
    "subject_type IN ('artifact','file','message','evidence_item','sealed_record',"
    "'run_record','agent_card','binder','packet','pack_record','saved_query')"
)
_NAME = "ck_review_queues_subject_type"


def upgrade() -> None:
    op.create_table(
        "saved_queries",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("sql", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("created_by_user_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_saved_queries_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_saved_queries")),
        sa.UniqueConstraint("tenant_id", "name", "version", name="uq_saved_queries_version"),
    )
    op.create_index("ix_saved_queries_tenant", "saved_queries", ["tenant_id", "name"])
    add_append_only_trigger("saved_queries")
    enable_tenant_rls("saved_queries")
    grant_table("saved_queries", append_only=True)
    op.execute(f"ALTER TABLE review_queues DROP CONSTRAINT IF EXISTS {_NAME}")
    op.execute(f"ALTER TABLE review_queues ADD CONSTRAINT {_NAME} CHECK ({_WIDE})")


def downgrade() -> None:
    op.execute(f"ALTER TABLE review_queues DROP CONSTRAINT IF EXISTS {_NAME}")
    op.execute(f"ALTER TABLE review_queues ADD CONSTRAINT {_NAME} CHECK ({_EARLIER}) NOT VALID")
    op.drop_index("ix_saved_queries_tenant", table_name="saved_queries")
    op.drop_table("saved_queries")

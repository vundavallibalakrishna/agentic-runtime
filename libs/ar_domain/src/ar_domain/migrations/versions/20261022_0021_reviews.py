"""reviews_signoffs

Revision ID: 0021
Revises: 0020
Create Date: 2026-10-22
"""

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from ar_domain.migrations.helpers import (
    add_append_only_trigger,
    add_updated_at_trigger,
    enable_tenant_rls,
    grant_tables,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SUBJECTS = (
    "subject_type IN ('artifact','file','message','evidence_item',"
    "'run_record','agent_card','binder','pack_record')"
)


def upgrade() -> None:
    op.create_table(
        "review_queues",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("slug", postgresql.CITEXT(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("subject_type", sa.Text(), nullable=False),
        sa.Column("levels", postgresql.JSONB(), nullable=False),
        sa.Column("statement_template", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(_SUBJECTS, name=op.f("ck_review_queues_subject_type")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "slug", name="uq_review_queues_slug"),
    )
    op.create_index("ix_review_queues_tenant", "review_queues", ["tenant_id"], unique=False)
    op.create_table(
        "review_items",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("queue_id", sa.UUID(), nullable=False),
        sa.Column("subject_type", sa.Text(), nullable=False),
        sa.Column("subject_id", sa.UUID(), nullable=False),
        sa.Column(
            "subject_ref", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("statement_text", sa.Text(), nullable=False),
        sa.Column("statement_hash", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("current_level", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("preparer_principal_type", sa.Text(), nullable=False),
        sa.Column("preparer_principal_id", sa.UUID(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('pending','in_review','signed','rejected','expired','superseded')",
            name=op.f("ck_review_items_status"),
        ),
        sa.CheckConstraint(
            "preparer_principal_type IN ('user','service_account','guest')",
            name=op.f("ck_review_items_preparer_principal_type"),
        ),
        sa.ForeignKeyConstraint(["queue_id"], ["review_queues.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_review_items_queue", "review_items", ["tenant_id", "queue_id", "status"], unique=False
    )
    op.create_index(
        "ix_review_items_subject",
        "review_items",
        ["tenant_id", "subject_type", "subject_id"],
        unique=False,
    )
    op.create_table(
        "signoffs",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("review_item_id", sa.UUID(), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("decision", sa.Text(), nullable=False),
        sa.Column("signer_principal_type", sa.Text(), nullable=False),
        sa.Column("signer_principal_id", sa.UUID(), nullable=False),
        sa.Column("signer_role_key", sa.Text(), nullable=True),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("statement_hash", sa.Text(), nullable=False),
        sa.Column("comment", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("step_up_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delegated_to_user_id", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "decision IN ('approve','reject','delegate')", name=op.f("ck_signoffs_decision")
        ),
        sa.CheckConstraint(
            "signer_principal_type IN ('user','guest')",
            name=op.f("ck_signoffs_signer_principal_type"),
        ),
        sa.ForeignKeyConstraint(["delegated_to_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["review_item_id"], ["review_items.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_signoffs_item", "signoffs", ["tenant_id", "review_item_id", "level"], unique=False
    )
    for table in ("review_queues", "review_items"):
        add_updated_at_trigger(table)
        enable_tenant_rls(table)
    add_append_only_trigger("signoffs")
    enable_tenant_rls("signoffs")
    grant_tables(
        ["review_queues", "review_items", "signoffs"],
        append_only=["signoffs"],
    )


def downgrade() -> None:
    op.drop_index("ix_signoffs_item", table_name="signoffs")
    op.drop_table("signoffs")
    op.drop_index("ix_review_items_subject", table_name="review_items")
    op.drop_index("ix_review_items_queue", table_name="review_items")
    op.drop_table("review_items")
    op.drop_index("ix_review_queues_tenant", table_name="review_queues")
    op.drop_table("review_queues")

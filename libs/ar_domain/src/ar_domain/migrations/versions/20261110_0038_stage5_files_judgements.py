"""Original file keys, chunk embedding models, rule sets and judgements.

Revision ID: 0038
Revises: 0037
Create Date: 2026-11-10

Expand only. ``object_key`` and ``embedding_model_id`` are nullable, so existing
rows keep working. Rule-set versions and judgements are append-only.
"""

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from ar_domain.migrations.helpers import (
    add_append_only_trigger,
    enable_tenant_rls,
    grant_tables,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0038"
down_revision: str | None = "0037"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW = ("rule_sets", "judgements")


def upgrade() -> None:
    op.add_column("library_documents", sa.Column("object_key", sa.Text(), nullable=True))
    op.add_column(
        "document_chunks",
        sa.Column("embedding_model_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_document_chunks_embedding_model_id_models"),
        "document_chunks",
        "models",
        ["embedding_model_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_table(
        "rule_sets",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("set_id", sa.Text(), nullable=False),
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column(
            "items",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("source_file_id", sa.UUID(), nullable=True),
        sa.Column("sha256", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_rule_sets_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_file_id"],
            ["library_documents.id"],
            name=op.f("fk_rule_sets_source_file_id_library_documents"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_rule_sets_created_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rule_sets")),
        sa.UniqueConstraint(
            "tenant_id",
            "set_id",
            "version",
            name="uq_rule_sets_version",
        ),
    )
    op.create_index("ix_rule_sets_tenant", "rule_sets", ["tenant_id", "set_id"])
    op.create_table(
        "judgements",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("rule_set_id", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("rule_set_version", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("item_id", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("verdict", sa.Text(), nullable=False),
        sa.Column("passage_id", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("quote", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("model_id", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("prompt_hash", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "verdict IN ('supported','not_supported','not_judged','failed')",
            name=op.f("ck_judgements_verdict"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_judgements_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["library_documents.id"],
            name=op.f("fk_judgements_document_id_library_documents"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_judgements_created_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_judgements")),
    )
    op.create_index("ix_judgements_document", "judgements", ["tenant_id", "document_id"])
    for table in _NEW:
        add_append_only_trigger(table)
        enable_tenant_rls(table)
    grant_tables(_NEW, append_only=_NEW)


def downgrade() -> None:
    op.drop_index("ix_judgements_document", table_name="judgements")
    op.drop_table("judgements")
    op.drop_index("ix_rule_sets_tenant", table_name="rule_sets")
    op.drop_table("rule_sets")
    op.drop_constraint(
        op.f("fk_document_chunks_embedding_model_id_models"),
        "document_chunks",
        type_="foreignkey",
    )
    op.drop_column("document_chunks", "embedding_model_id")
    op.drop_column("library_documents", "object_key")

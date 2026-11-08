"""A durable table for tool-search embeddings, per tenant and model.

Revision ID: 0035
Revises: 0034

Tool search kept its embeddings only in each process's memory, so the first search
after a restart was ranked by words until the catalogue was embedded again (OQ-106).
This table keeps a vector per tenant, embedding model and tool text, so a new process
ranks by meaning as soon as its tenant is hydrated. The vector is JSON (the cosine is
computed in Python); a changed description or model has a new ``text_hash``.
"""

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

from ar_domain.migrations.helpers import add_updated_at_trigger, enable_tenant_rls, grant_tables

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0035"
down_revision: str | None = "0034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tool_search_vectors",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("model_id", sa.Text(), nullable=False),
        sa.Column("text_hash", sa.Text(), nullable=False),
        sa.Column("vector", sa.dialects.postgresql.JSONB(), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_tool_search_vectors_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tool_search_vectors")),
    )
    op.create_index(
        "uq_tool_search_vectors_text",
        "tool_search_vectors",
        ["tenant_id", "model_id", "text_hash"],
        unique=True,
    )
    enable_tenant_rls("tool_search_vectors")
    add_updated_at_trigger("tool_search_vectors")
    grant_tables(["tool_search_vectors"])


def downgrade() -> None:
    op.drop_index("uq_tool_search_vectors_text", table_name="tool_search_vectors")
    op.drop_table("tool_search_vectors")

"""memory

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-22 08:07:04.952203
"""

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from ar_domain.migrations.helpers import add_updated_at_trigger, enable_tenant_rls, grant_tables

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "memory_facts",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("agent_id", sa.UUID(), nullable=True),
        sa.Column("team_id", sa.UUID(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), server_default=sa.text("'fact'"), nullable=False),
        sa.Column("embedding", Vector(dim=1024), nullable=True),
        sa.Column("embedding_model_id", sa.UUID(), nullable=True),
        sa.Column("source_kind", sa.Text(), nullable=False),
        sa.Column(
            "source_ref",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("trust_level", sa.Text(), server_default=sa.text("'high'"), nullable=False),
        sa.Column("confidence", sa.REAL(), server_default=sa.text("1.0"), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'active'"), nullable=False),
        sa.Column("superseded_by_id", sa.UUID(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_recalled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recall_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
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
            "(scope = 'user' AND user_id IS NOT NULL) "
            "OR (scope = 'agent' AND agent_id IS NOT NULL) "
            "OR (scope = 'team' AND team_id IS NOT NULL) "
            "OR (scope = 'agent_user' AND agent_id IS NOT NULL AND user_id IS NOT NULL)",
            name=op.f("ck_memory_facts_scope_shape"),
        ),
        sa.CheckConstraint(
            "category IN ('preference','fact','instruction','lesson','contact','glossary')",
            name=op.f("ck_memory_facts_category"),
        ),
        sa.CheckConstraint(
            "scope IN ('user','agent','team','agent_user')",
            name=op.f("ck_memory_facts_scope"),
        ),
        sa.CheckConstraint(
            "source_kind IN ('explicit','extracted','tool_output','admin','import')",
            name=op.f("ck_memory_facts_source_kind"),
        ),
        sa.CheckConstraint(
            "status IN ('active','pending_review','superseded','deleted')",
            name=op.f("ck_memory_facts_status"),
        ),
        sa.CheckConstraint(
            "trust_level IN ('high','low')", name=op.f("ck_memory_facts_trust_level")
        ),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name=op.f("ck_memory_facts_confidence")),
        sa.CheckConstraint("length(content) <= 1000", name=op.f("ck_memory_facts_content_len")),
        sa.ForeignKeyConstraint(
            ["agent_id"],
            ["agents.id"],
            name=op.f("fk_memory_facts_agent_id_agents"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_memory_facts_created_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["embedding_model_id"],
            ["models.id"],
            name=op.f("fk_memory_facts_embedding_model_id_models"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["superseded_by_id"],
            ["memory_facts.id"],
            name=op.f("fk_memory_facts_superseded_by_id_memory_facts"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["team_id"],
            ["teams.id"],
            name=op.f("fk_memory_facts_team_id_teams"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_memory_facts_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_memory_facts_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_memory_facts")),
    )
    op.create_index(
        "ix_memory_agent",
        "memory_facts",
        ["tenant_id", "agent_id"],
        unique=False,
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_index(
        "ix_memory_embedding",
        "memory_facts",
        ["embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_index(
        "ix_memory_team",
        "memory_facts",
        ["tenant_id", "team_id"],
        unique=False,
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_index(
        "ix_memory_user",
        "memory_facts",
        ["tenant_id", "user_id"],
        unique=False,
        postgresql_where=sa.text("status = 'active'"),
    )
    enable_tenant_rls("memory_facts")
    add_updated_at_trigger("memory_facts")
    grant_tables(["memory_facts"])


def downgrade() -> None:
    op.drop_index(
        "ix_memory_user", table_name="memory_facts", postgresql_where=sa.text("status = 'active'")
    )
    op.drop_index(
        "ix_memory_team", table_name="memory_facts", postgresql_where=sa.text("status = 'active'")
    )
    op.drop_index(
        "ix_memory_embedding",
        table_name="memory_facts",
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
        postgresql_where=sa.text("status = 'active'"),
    )
    op.drop_index(
        "ix_memory_agent", table_name="memory_facts", postgresql_where=sa.text("status = 'active'")
    )
    op.drop_table("memory_facts")

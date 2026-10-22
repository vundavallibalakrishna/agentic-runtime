"""channels

Revision ID: 0018
Revises: 0017
Create Date: 2026-10-22 18:00:00.000000
"""

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from ar_domain.migrations.helpers import add_updated_at_trigger, enable_tenant_rls, grant_tables

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "channel_integrations",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "config",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("secret_ref_id", sa.UUID(), nullable=True),
        sa.Column("default_agent_id", sa.UUID(), nullable=True),
        sa.Column(
            "agent_routing",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("status", sa.Text(), server_default=sa.text("'active'"), nullable=False),
        sa.Column("status_detail", sa.Text(), nullable=True),
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
            "kind IN ('slack','teams','email','widget')", name=op.f("ck_channel_integrations_kind")
        ),
        sa.CheckConstraint(
            "status IN ('active','disabled','error')", name=op.f("ck_channel_integrations_status")
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["default_agent_id"], ["agents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["secret_ref_id"], ["secret_refs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "kind", "name", name="uq_channel_integrations_kind_name"),
    )
    op.create_table(
        "channel_identities",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("integration_id", sa.UUID(), nullable=False),
        sa.Column("external_user_id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("match_method", sa.Text(), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "match_method IN ('email','scim','manual_link')",
            name=op.f("ck_channel_identities_match_method"),
        ),
        sa.ForeignKeyConstraint(
            ["integration_id"], ["channel_integrations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "integration_id", "external_user_id", name="uq_channel_identities_external"
        ),
    )
    op.create_table(
        "channel_threads",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("integration_id", sa.UUID(), nullable=False),
        sa.Column("external_channel_id", sa.Text(), nullable=False),
        sa.Column("external_thread_id", sa.Text(), nullable=False),
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["integration_id"], ["channel_integrations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "integration_id",
            "external_channel_id",
            "external_thread_id",
            name="uq_channel_threads_external",
        ),
    )
    op.create_table(
        "channel_posts",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("integration_id", sa.UUID(), nullable=True),
        sa.Column("thread_id", sa.UUID(), nullable=True),
        sa.Column("direction", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("external_message_id", sa.Text(), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'posted'"), nullable=False),
        sa.Column(
            "detail",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "direction IN ('inbound','outbound')", name=op.f("ck_channel_posts_direction")
        ),
        sa.CheckConstraint(
            "kind IN ('slack','teams','email','widget','webhook')",
            name=op.f("ck_channel_posts_kind"),
        ),
        sa.CheckConstraint(
            "status IN ('posted','failed','pending')", name=op.f("ck_channel_posts_status")
        ),
        sa.ForeignKeyConstraint(
            ["integration_id"], ["channel_integrations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["thread_id"], ["channel_threads.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_channel_posts_tenant", "channel_posts", ["tenant_id", "created_at"])
    enable_tenant_rls("channel_integrations")
    enable_tenant_rls("channel_identities")
    enable_tenant_rls("channel_threads")
    enable_tenant_rls("channel_posts")
    add_updated_at_trigger("channel_integrations")
    grant_tables(["channel_integrations", "channel_identities", "channel_threads", "channel_posts"])


def downgrade() -> None:
    op.drop_index("ix_channel_posts_tenant", table_name="channel_posts")
    op.drop_table("channel_posts")
    op.drop_table("channel_threads")
    op.drop_table("channel_identities")
    op.drop_table("channel_integrations")

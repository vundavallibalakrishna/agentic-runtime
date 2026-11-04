"""Durable service connections and registry state.

Revision ID: 0025
Revises: 0024
Create Date: 2026-10-29
"""

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from ar_domain.migrations.helpers import (
    add_updated_at_trigger,
    enable_tenant_rls,
    grant_tables,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0025"
down_revision: str | None = "0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_EMPTY = r"'\x'::bytea"


def upgrade() -> None:
    op.add_column("data_connections", sa.Column("dsn_ciphertext", sa.LargeBinary(), nullable=True))
    op.add_column("tool_servers", sa.Column("last_error", sa.Text(), nullable=True))
    op.add_column("tool_server_versions", sa.Column("discovery_error", sa.Text(), nullable=True))
    op.add_column("tool_server_versions", sa.Column("upstream_hash", sa.Text(), nullable=True))
    op.add_column("tools", sa.Column("last_error", sa.Text(), nullable=True))
    op.create_table(
        "service_connections",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("owner_user_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'active'"), nullable=False),
        sa.Column("header_name", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("username", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("token_url", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("authorize_url", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("client_id", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column(
            "scopes", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False
        ),
        sa.Column("probe_url", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("secret", sa.LargeBinary(), server_default=sa.text(_EMPTY), nullable=False),
        sa.Column("access_token", sa.LargeBinary(), server_default=sa.text(_EMPTY), nullable=False),
        sa.Column(
            "refresh_token", sa.LargeBinary(), server_default=sa.text(_EMPTY), nullable=False
        ),
        sa.Column("expires_at", sa.Text(), nullable=True),
        sa.Column("last_tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
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
            "kind IN ('api_key','bearer','basic','oauth_authorization_code',"
            "'oauth_client_credentials')",
            name=op.f("ck_service_connections_kind"),
        ),
        sa.CheckConstraint(
            "status IN ('active','revoked','expired')",
            name=op.f("ck_service_connections_status"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name=op.f("fk_service_connections_owner_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_service_connections_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_service_connections")),
    )
    op.create_index(
        "ux_service_connections_name",
        "service_connections",
        ["tenant_id", sa.literal_column("lower(name)")],
        unique=True,
    )
    add_updated_at_trigger("service_connections")
    enable_tenant_rls("service_connections")
    grant_tables(["service_connections"])


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS service_connections CASCADE")
    op.drop_column("tools", "last_error")
    op.drop_column("tool_server_versions", "upstream_hash")
    op.drop_column("tool_server_versions", "discovery_error")
    op.drop_column("tool_servers", "last_error")
    op.drop_column("data_connections", "dsn_ciphertext")

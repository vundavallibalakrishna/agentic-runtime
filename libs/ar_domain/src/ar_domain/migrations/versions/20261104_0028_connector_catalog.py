"""Connector installs, OAuth state, named secrets and grant ciphertext.

Revision ID: 0028
Revises: 0027
Create Date: 2026-11-04
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

revision: str = "0028"
down_revision: str | None = "0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_EMPTY = r"'\x'::bytea"


def upgrade() -> None:
    op.add_column(
        "credential_grants",
        sa.Column(
            "access_ciphertext",
            sa.LargeBinary(),
            server_default=sa.text(_EMPTY),
            nullable=False,
        ),
    )
    op.add_column(
        "credential_grants",
        sa.Column(
            "refresh_ciphertext",
            sa.LargeBinary(),
            server_default=sa.text(_EMPTY),
            nullable=False,
        ),
    )
    op.alter_column("credential_grants", "secret_ref_id", existing_type=sa.UUID(), nullable=True)
    op.create_table(
        "connector_installs",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("owner_user_id", sa.UUID(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("connection_name", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("connection_id", sa.UUID(), nullable=True),
        sa.Column("status", sa.Text(), server_default=sa.text("'installed'"), nullable=False),
        sa.Column(
            "disabled_tools",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "config",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("last_tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
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
            "status IN ('installed','disabled')",
            name=op.f("ck_connector_installs_status"),
        ),
        sa.ForeignKeyConstraint(
            ["connection_id"],
            ["service_connections.id"],
            name=op.f("fk_connector_installs_connection_id_service_connections"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name=op.f("fk_connector_installs_owner_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_connector_installs_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_connector_installs")),
    )
    op.create_index(
        "ux_connector_installs_owner_slug",
        "connector_installs",
        ["tenant_id", "owner_user_id", "slug"],
        unique=True,
    )
    op.create_table(
        "oauth_states",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("provider_id", sa.UUID(), nullable=True),
        sa.Column("connection_id", sa.UUID(), nullable=True),
        sa.Column("kind", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("verifier", sa.LargeBinary(), server_default=sa.text(_EMPTY), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["connection_id"],
            ["service_connections.id"],
            name=op.f("fk_oauth_states_connection_id_service_connections"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["provider_id"],
            ["credential_providers.id"],
            name=op.f("fk_oauth_states_provider_id_credential_providers"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_oauth_states_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_oauth_states_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_oauth_states")),
    )
    op.create_index("ix_oauth_states_tenant", "oauth_states", ["tenant_id"])
    op.create_table(
        "named_secrets",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("ciphertext", sa.LargeBinary(), server_default=sa.text(_EMPTY), nullable=False),
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
            name=op.f("fk_named_secrets_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_named_secrets")),
    )
    op.create_index(
        "ux_named_secrets_name",
        "named_secrets",
        ["tenant_id", sa.literal_column("lower(name)")],
        unique=True,
    )
    add_updated_at_trigger("connector_installs")
    add_updated_at_trigger("named_secrets")
    enable_tenant_rls("connector_installs")
    enable_tenant_rls("oauth_states")
    enable_tenant_rls("named_secrets")
    grant_tables(["connector_installs", "oauth_states", "named_secrets"])


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS named_secrets CASCADE")
    op.execute("DROP TABLE IF EXISTS oauth_states CASCADE")
    op.execute("DROP TABLE IF EXISTS connector_installs CASCADE")
    op.execute("DELETE FROM credential_grants WHERE secret_ref_id IS NULL")
    op.alter_column("credential_grants", "secret_ref_id", existing_type=sa.UUID(), nullable=False)
    op.drop_column("credential_grants", "refresh_ciphertext")
    op.drop_column("credential_grants", "access_ciphertext")

"""secrets

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-20
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

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "encrypted_secrets",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("key_id", sa.Text(), nullable=False),
        sa.Column("wrapped_dek", sa.LargeBinary(), nullable=False),
        sa.Column("nonce", sa.LargeBinary(), nullable=False),
        sa.Column("ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_encrypted_secrets_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_encrypted_secrets")),
    )
    op.create_index("ix_encrypted_secrets_tenant", "encrypted_secrets", ["tenant_id"], unique=False)
    op.create_table(
        "secret_refs",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("backend", sa.Text(), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("description", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("owner_user_id", sa.UUID(), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True),
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
            "backend IN ('vault','db_encrypted')", name=op.f("ck_secret_refs_backend")
        ),
        sa.CheckConstraint(
            "kind IN ('api_key','basic_auth','bearer_token','oauth_client','oauth_refresh_token','db_dsn','webhook_secret','generic')",
            name=op.f("ck_secret_refs_kind"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_secret_refs_created_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name=op.f("fk_secret_refs_owner_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_secret_refs_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_secret_refs")),
        sa.UniqueConstraint(
            "tenant_id",
            "owner_user_id",
            "name",
            name="uq_secret_refs_name",
            postgresql_nulls_not_distinct=True,
        ),
    )
    op.create_table(
        "credential_providers",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("slug", postgresql.CITEXT(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("authorize_url", sa.Text(), nullable=True),
        sa.Column("token_url", sa.Text(), nullable=True),
        sa.Column("client_id", sa.Text(), nullable=True),
        sa.Column("client_secret_ref_id", sa.UUID(), nullable=True),
        sa.Column(
            "default_scopes",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column("token_exchange_audience", sa.Text(), nullable=True),
        sa.Column(
            "extra",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("status", sa.Text(), server_default=sa.text("'active'"), nullable=False),
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
            "kind IN ('oauth2','api_key','token_exchange')",
            name=op.f("ck_credential_providers_kind"),
        ),
        sa.CheckConstraint(
            "status IN ('active','disabled')", name=op.f("ck_credential_providers_status")
        ),
        sa.ForeignKeyConstraint(
            ["client_secret_ref_id"],
            ["secret_refs.id"],
            name=op.f("fk_credential_providers_client_secret_ref_id_secret_refs"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_credential_providers_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_credential_providers")),
        sa.UniqueConstraint("tenant_id", "slug", name="uq_credential_providers_slug"),
    )
    op.create_table(
        "credential_grants",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("provider_id", sa.UUID(), nullable=False),
        sa.Column(
            "scopes",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column("secret_ref_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'active'"), nullable=False),
        sa.Column("external_account_label", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
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
            "status IN ('active','expired','revoked','error')",
            name=op.f("ck_credential_grants_status"),
        ),
        sa.ForeignKeyConstraint(
            ["provider_id"],
            ["credential_providers.id"],
            name=op.f("fk_credential_grants_provider_id_credential_providers"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["secret_ref_id"],
            ["secret_refs.id"],
            name=op.f("fk_credential_grants_secret_ref_id_secret_refs"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_credential_grants_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_credential_grants_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_credential_grants")),
        sa.UniqueConstraint("tenant_id", "user_id", "provider_id", name="uq_credential_grants"),
    )
    enable_tenant_rls("encrypted_secrets")
    add_updated_at_trigger("secret_refs")
    enable_tenant_rls("secret_refs")
    add_updated_at_trigger("credential_providers")
    enable_tenant_rls("credential_providers")
    add_updated_at_trigger("credential_grants")
    enable_tenant_rls("credential_grants")

    op.create_foreign_key(
        "fk_idp_secret",
        "identity_providers",
        "secret_refs",
        ["secret_ref_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_webhook_secret",
        "outbound_webhooks",
        "secret_refs",
        ["secret_ref_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    grant_tables(["encrypted_secrets", "secret_refs", "credential_providers", "credential_grants"])


def downgrade() -> None:
    op.drop_constraint("fk_webhook_secret", "outbound_webhooks", type_="foreignkey")
    op.drop_constraint("fk_idp_secret", "identity_providers", type_="foreignkey")
    op.execute("DROP TABLE IF EXISTS credential_grants CASCADE")
    op.execute("DROP TABLE IF EXISTS credential_providers CASCADE")
    op.execute("DROP TABLE IF EXISTS secret_refs CASCADE")
    op.execute("DROP TABLE IF EXISTS encrypted_secrets CASCADE")

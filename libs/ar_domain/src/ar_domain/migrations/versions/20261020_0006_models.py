"""models

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-20
"""

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from ar_domain.migrations.helpers import (
    add_updated_at_trigger,
    enable_platform_or_own_rls,
    grant_tables,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ZERO = "00000000-0000-0000-0000-000000000000"


def _ts() -> sa.Column[object]:
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
    )


def upgrade() -> None:
    op.create_table(
        "model_providers",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("base_url", sa.Text(), nullable=False),
        sa.Column("api_key_ref_id", sa.UUID(), nullable=True),
        sa.Column(
            "headers", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column("timeout_s", sa.Integer(), server_default=sa.text("120"), nullable=False),
        sa.Column("max_concurrency", sa.Integer(), server_default=sa.text("64"), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'active'"), nullable=False),
        sa.Column(
            "health", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        _ts(),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "kind IN ('openai_compatible','vllm','tei','fake')",
            name=op.f("ck_model_providers_kind"),
        ),
        sa.CheckConstraint(
            "timeout_s BETWEEN 1 AND 900", name=op.f("ck_model_providers_timeout_s")
        ),
        sa.CheckConstraint(
            "status IN ('active','disabled')", name=op.f("ck_model_providers_status")
        ),
        sa.ForeignKeyConstraint(
            ["api_key_ref_id"],
            ["secret_refs.id"],
            name=op.f("fk_model_providers_api_key_ref_id_secret_refs"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_model_providers_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_model_providers")),
    )
    op.create_index("ix_model_providers_tenant", "model_providers", ["tenant_id"], unique=False)
    op.create_table(
        "models",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=True),
        sa.Column("provider_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("upstream_model", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column(
            "capabilities",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column("context_window", sa.Integer(), nullable=True),
        sa.Column("max_output_tokens", sa.Integer(), nullable=True),
        sa.Column("embedding_dimensions", sa.Integer(), nullable=True),
        sa.Column(
            "price_input_micros_per_mtok",
            sa.BigInteger(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "price_output_micros_per_mtok",
            sa.BigInteger(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("licence", sa.Text(), server_default=sa.text("''"), nullable=False),
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
        sa.CheckConstraint("kind IN ('chat','embedding','rerank')", name=op.f("ck_models_kind")),
        sa.CheckConstraint(
            "status IN ('active','disabled','deprecated')", name=op.f("ck_models_status")
        ),
        sa.ForeignKeyConstraint(
            ["provider_id"],
            ["model_providers.id"],
            name=op.f("fk_models_provider_id_model_providers"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_models_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_models")),
    )
    op.create_index("ix_models_tenant", "models", ["tenant_id"], unique=False)
    op.create_table(
        "model_aliases",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=True),
        sa.Column("alias", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("primary_model_id", sa.UUID(), nullable=False),
        sa.Column(
            "fallback_model_ids",
            postgresql.ARRAY(postgresql.UUID()),
            server_default=sa.text("'{}'::uuid[]"),
            nullable=False,
        ),
        sa.Column(
            "traffic_split",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "default_params",
            postgresql.JSONB(),
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
            "alias ~ '^[a-z][a-z0-9_-]{1,40}$'", name=op.f("ck_model_aliases_alias")
        ),
        sa.CheckConstraint(
            "kind IN ('chat','embedding','rerank')", name=op.f("ck_model_aliases_kind")
        ),
        sa.CheckConstraint("status IN ('active','disabled')", name=op.f("ck_model_aliases_status")),
        sa.ForeignKeyConstraint(
            ["primary_model_id"],
            ["models.id"],
            name=op.f("fk_model_aliases_primary_model_id_models"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_model_aliases_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_model_aliases")),
    )
    op.create_index(
        "ux_model_aliases",
        "model_aliases",
        [
            sa.literal_column(f"coalesce(tenant_id, '{_ZERO}'::uuid)"),
            "alias",
        ],
        unique=True,
    )
    for table in ("model_providers", "models", "model_aliases"):
        add_updated_at_trigger(table)
        enable_platform_or_own_rls(table)
    grant_tables(["model_providers", "models", "model_aliases"])


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS model_aliases CASCADE")
    op.execute("DROP TABLE IF EXISTS models CASCADE")
    op.execute("DROP TABLE IF EXISTS model_providers CASCADE")

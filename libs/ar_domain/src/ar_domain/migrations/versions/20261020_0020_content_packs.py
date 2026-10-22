"""content_packs

Revision ID: 0020
Revises: 0010
Create Date: 2026-10-22

0020 revises 0010 until revisions 0011-0019 exist. The next migration task
points this revision at the new head (OQ-34). The published-version trigger
allows the single transition published → superseded, which spec 05 requires.
"""

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from ar_domain.migrations.helpers import enable_tenant_rls, grant_tables

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0020"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "installed_packs",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("pack_id", sa.Text(), nullable=False),
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'installed'"), nullable=False),
        sa.Column("manifest", postgresql.JSONB(), nullable=False),
        sa.Column("manifest_hash", sa.Text(), nullable=False),
        sa.Column("signature", sa.Text(), nullable=True),
        sa.Column("signature_key_id", sa.Text(), nullable=True),
        sa.Column("installed_by", sa.UUID(), nullable=True),
        sa.Column(
            "installed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "pack_id ~ '^[a-z][a-z0-9_]{1,40}$'",
            name=op.f("ck_installed_packs_pack_id"),
        ),
        sa.CheckConstraint(
            "status IN ('installed','uninstalled')",
            name=op.f("ck_installed_packs_status"),
        ),
        sa.ForeignKeyConstraint(
            ["installed_by"],
            ["users.id"],
            name=op.f("fk_installed_packs_installed_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_installed_packs_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_installed_packs")),
        sa.UniqueConstraint("tenant_id", "pack_id", "version", name="uq_installed_packs_version"),
    )
    op.create_index(
        "ix_installed_packs_tenant", "installed_packs", ["tenant_id", "pack_id"], unique=False
    )
    op.create_table(
        "installed_pack_resources",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("pack_row_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("resource_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["pack_row_id"],
            ["installed_packs.id"],
            name=op.f("fk_installed_pack_resources_pack_row_id_installed_packs"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_installed_pack_resources_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_installed_pack_resources")),
        sa.UniqueConstraint(
            "pack_row_id",
            "kind",
            "slug",
            name="uq_installed_pack_resources_identity",
        ),
    )
    op.create_index(
        "ix_installed_pack_resources_tenant",
        "installed_pack_resources",
        ["tenant_id"],
        unique=False,
    )
    for table in ("installed_packs", "installed_pack_resources"):
        enable_tenant_rls(table)
    grant_tables(["installed_packs", "installed_pack_resources"])
    op.execute(
        """
        CREATE OR REPLACE FUNCTION forbid_published_agent_version_update() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
          IF OLD.state = 'published' AND NEW.state IS DISTINCT FROM 'superseded' THEN
            RAISE EXCEPTION 'published agent versions are immutable';
          END IF;
          IF OLD.state = 'published' AND NEW.state = 'superseded' THEN
            RETURN NEW;
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )


def downgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION forbid_published_agent_version_update() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
          IF OLD.state = 'published' THEN
            RAISE EXCEPTION 'published agent versions are immutable';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
    op.execute("DROP TABLE IF EXISTS installed_pack_resources CASCADE")
    op.execute("DROP TABLE IF EXISTS installed_packs CASCADE")

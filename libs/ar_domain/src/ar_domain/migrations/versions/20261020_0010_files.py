"""files

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-20
"""

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from ar_domain.migrations.helpers import add_updated_at_trigger, enable_tenant_rls, grant_tables

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "files",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("owner_user_id", sa.UUID(), nullable=True),
        sa.Column("conversation_id", sa.UUID(), nullable=True),
        sa.Column("run_id", sa.UUID(), nullable=True),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("mime_type", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("sha256", sa.Text(), nullable=True),
        sa.Column("object_key", sa.Text(), nullable=False),
        sa.Column(
            "classification", sa.Text(), server_default=sa.text("'internal'"), nullable=False
        ),
        sa.Column("status", sa.Text(), server_default=sa.text("'pending_upload'"), nullable=False),
        sa.Column("scan_status", sa.Text(), server_default=sa.text("'pending'"), nullable=False),
        sa.Column(
            "preview", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column("retention_until", sa.DateTime(timezone=True), nullable=True),
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
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "kind IN ('upload','artifact','tool_result','sandbox_snapshot','knowledge_raw',"
            "'knowledge_parsed','skill_asset','avatar','export','openapi_spec','eval_dataset',"
            "'event_payload')",
            name=op.f("ck_files_kind"),
        ),
        sa.CheckConstraint(
            "classification IN ('public','internal','confidential','restricted')",
            name=op.f("ck_files_classification"),
        ),
        sa.CheckConstraint(
            "status IN ('pending_upload','ready','quarantined','deleted')",
            name=op.f("ck_files_status"),
        ),
        sa.CheckConstraint(
            "scan_status IN ('pending','clean','infected','skipped','error')",
            name=op.f("ck_files_scan_status"),
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            name=op.f("fk_files_conversation_id_conversations"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name=op.f("fk_files_owner_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["runs.id"], name=op.f("fk_files_run_id_runs"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_files_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_files")),
        sa.UniqueConstraint("object_key", name=op.f("uq_files_object_key")),
    )
    op.create_index(
        "ix_files_owner",
        "files",
        ["tenant_id", "owner_user_id", sa.literal_column("created_at DESC")],
        unique=False,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_files_conversation", "files", ["tenant_id", "conversation_id"], unique=False
    )
    op.create_index(
        "ix_files_retention",
        "files",
        ["retention_until"],
        unique=False,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_foreign_key(
        "fk_agents_avatar",
        "agents",
        "files",
        ["avatar_file_id"],
        ["id"],
        ondelete="SET NULL",
    )
    add_updated_at_trigger("files")
    enable_tenant_rls("files")
    grant_tables(["files"])


def downgrade() -> None:
    op.drop_constraint("fk_agents_avatar", "agents", type_="foreignkey")
    op.execute("DROP TABLE IF EXISTS files CASCADE")

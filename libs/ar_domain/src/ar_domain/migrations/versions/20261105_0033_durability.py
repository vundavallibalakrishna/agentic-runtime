"""File bytes, workspace files, job progress and A2A push configs.

Revision ID: 0033
Revises: 0032
Create Date: 2026-11-05
"""

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

from ar_domain.migrations.helpers import add_updated_at_trigger, enable_tenant_rls, grant_tables

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0033"
down_revision: str | None = "0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = ("file_blobs", "workspace_files", "job_progress", "a2a_push_configs")


def upgrade() -> None:
    op.create_table(
        "file_blobs",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("owner_user_id", sa.UUID(), nullable=True),
        sa.Column("conversation_id", sa.UUID(), nullable=True),
        sa.Column("run_id", sa.UUID(), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("mime_type", sa.Text(), nullable=False),
        sa.Column("sha256", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("kind", sa.Text(), server_default=sa.text("'upload'"), nullable=False),
        sa.Column("body", sa.LargeBinary(), nullable=False),
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
            name=op.f("fk_file_blobs_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_file_blobs")),
    )
    op.create_index("ix_file_blobs_tenant", "file_blobs", ["tenant_id"])
    op.create_table(
        "workspace_files",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("body", sa.LargeBinary(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
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
            ["run_id"],
            ["runs.id"],
            name=op.f("fk_workspace_files_run_id_runs"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_workspace_files_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workspace_files")),
    )
    op.create_index(
        "uq_workspace_files_run_path", "workspace_files", ["run_id", "path"], unique=True
    )
    op.create_index("ix_workspace_files_run", "workspace_files", ["tenant_id", "run_id"])
    op.create_table(
        "job_progress",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("run_id", sa.UUID(), nullable=True),
        sa.Column("conversation_id", sa.UUID(), nullable=True),
        sa.Column("tool_name", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("completed", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("total", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'running'"), nullable=False),
        sa.Column("detail", sa.Text(), server_default=sa.text("''"), nullable=False),
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
            "kind IN ('ocr','pdf','query','workspace')",
            name="kind",
        ),
        sa.CheckConstraint(
            "status IN ('running','completed','interrupted','failed')",
            name="status",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["runs.id"],
            name=op.f("fk_job_progress_run_id_runs"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_job_progress_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_job_progress")),
    )
    op.create_index(
        "ix_job_progress_conversation", "job_progress", ["tenant_id", "conversation_id"]
    )
    op.create_table(
        "a2a_push_configs",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("task_id", sa.UUID(), nullable=False),
        sa.Column("key_id", sa.UUID(), nullable=False),
        sa.Column("config_id", sa.Text(), server_default=sa.text("'default'"), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("token", sa.Text(), server_default=sa.text("''"), nullable=False),
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
            ["key_id"],
            ["agent_api_keys.id"],
            name=op.f("fk_a2a_push_configs_key_id_agent_api_keys"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["a2a_tasks.id"],
            name=op.f("fk_a2a_push_configs_task_id_a2a_tasks"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_a2a_push_configs_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_a2a_push_configs")),
    )
    op.create_index(
        "uq_a2a_push_configs_task_config",
        "a2a_push_configs",
        ["task_id", "config_id"],
        unique=True,
    )
    op.create_index("ix_a2a_push_configs_task", "a2a_push_configs", ["tenant_id", "task_id"])
    for table in _TABLES:
        add_updated_at_trigger(table)
        enable_tenant_rls(table)
    grant_tables(list(_TABLES))


def downgrade() -> None:
    op.drop_index("ix_a2a_push_configs_task", table_name="a2a_push_configs")
    op.drop_index("uq_a2a_push_configs_task_config", table_name="a2a_push_configs")
    op.drop_table("a2a_push_configs")
    op.drop_index("ix_job_progress_conversation", table_name="job_progress")
    op.drop_table("job_progress")
    op.drop_index("ix_workspace_files_run", table_name="workspace_files")
    op.drop_index("uq_workspace_files_run_path", table_name="workspace_files")
    op.drop_table("workspace_files")
    op.drop_index("ix_file_blobs_tenant", table_name="file_blobs")
    op.drop_table("file_blobs")

"""sod_constraints

Revision ID: 0022
Revises: 0021
Create Date: 2026-10-22
"""

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

from ar_domain.migrations.helpers import add_updated_at_trigger, enable_tenant_rls, grant_tables

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sod_constraints",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.Text(), server_default=sa.text("'conflicting_roles'"), nullable=False),
        sa.Column("role_a", sa.Text(), nullable=False),
        sa.Column("role_b", sa.Text(), nullable=False),
        sa.Column("applies_to", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
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
        sa.CheckConstraint("kind IN ('conflicting_roles')", name=op.f("ck_sod_constraints_kind")),
        sa.CheckConstraint(
            "applies_to IN ('approval','signoff','both')",
            name=op.f("ck_sod_constraints_applies_to"),
        ),
        sa.CheckConstraint("role_a <> role_b", name=op.f("ck_sod_constraints_roles_differ")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "role_a", "role_b", "applies_to", name="uq_sod_constraints_roles"
        ),
    )
    op.create_index("ix_sod_constraints_tenant", "sod_constraints", ["tenant_id"], unique=False)
    add_updated_at_trigger("sod_constraints")
    enable_tenant_rls("sod_constraints")
    grant_tables(["sod_constraints"])


def downgrade() -> None:
    op.drop_index("ix_sod_constraints_tenant", table_name="sod_constraints")
    op.drop_table("sod_constraints")

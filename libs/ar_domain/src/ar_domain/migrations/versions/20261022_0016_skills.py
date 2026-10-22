"""skills

Revision ID: 0016
Revises: 0015
Create Date: 2026-10-22 09:50:00.000000
"""

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from ar_domain.migrations.helpers import add_updated_at_trigger, enable_tenant_rls, grant_tables

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_IMMUTABLE = """
CREATE FUNCTION skill_versions_immutable() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.version >= 1 THEN
    RAISE EXCEPTION 'skill version % is immutable', OLD.version;
  END IF;
  IF TG_OP = 'DELETE' THEN
    RETURN OLD;
  END IF;
  RETURN NEW;
END;
$$
"""


def upgrade() -> None:
    op.create_table(
        "skills",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("slug", postgresql.CITEXT(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("owner_user_id", sa.UUID(), nullable=True),
        sa.Column("owner_team_id", sa.UUID(), nullable=True),
        sa.Column("visibility", sa.Text(), server_default=sa.text("'tenant'"), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'draft'"), nullable=False),
        sa.Column("published_version_id", sa.UUID(), nullable=True),
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
        sa.CheckConstraint("slug ~ '^[a-z0-9][a-z0-9-]{1,62}$'", name=op.f("ck_skills_slug")),
        sa.CheckConstraint("length(description) <= 500", name=op.f("ck_skills_description_len")),
        sa.CheckConstraint(
            "visibility IN ('private','team','tenant')", name=op.f("ck_skills_visibility")
        ),
        sa.CheckConstraint(
            "status IN ('draft','published','archived')", name=op.f("ck_skills_status")
        ),
        sa.ForeignKeyConstraint(["owner_team_id"], ["teams.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "slug", name="uq_skills_slug"),
    )
    op.create_table(
        "skill_versions",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("skill_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("instructions_md", sa.Text(), nullable=False),
        sa.Column(
            "assets",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "required_tools",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column("hash", sa.Text(), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("version >= 0", name=op.f("ck_skill_versions_version_non_negative")),
        sa.CheckConstraint(
            "length(instructions_md) <= 50000",
            name=op.f("ck_skill_versions_instructions_len"),
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["skill_id"], ["skills.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("skill_id", "version", name="uq_skill_versions_skill_version"),
    )
    op.create_foreign_key(
        "fk_skills_published",
        "skills",
        "skill_versions",
        ["published_version_id"],
        ["id"],
        deferrable=True,
        initially="DEFERRED",
    )
    op.execute(_IMMUTABLE)
    op.execute(
        "CREATE TRIGGER skill_versions_immutable BEFORE UPDATE OR DELETE ON skill_versions "
        "FOR EACH ROW EXECUTE FUNCTION skill_versions_immutable()"
    )
    enable_tenant_rls("skills")
    enable_tenant_rls("skill_versions")
    add_updated_at_trigger("skills")
    grant_tables(["skills", "skill_versions"])


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS skill_versions_immutable ON skill_versions")
    op.execute("DROP FUNCTION IF EXISTS skill_versions_immutable()")
    op.drop_constraint("fk_skills_published", "skills", type_="foreignkey")
    op.drop_table("skill_versions")
    op.drop_table("skills")

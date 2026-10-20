"""Extensions, RLS helpers and role grants.

Revision ID: 0001
Revises:
Create Date: 2026-10-20
"""

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ar_owner') THEN
            CREATE ROLE ar_owner LOGIN PASSWORD 'ar_owner' SUPERUSER BYPASSRLS;
          END IF;
          IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ar_app') THEN
            CREATE ROLE ar_app LOGIN PASSWORD 'ar_app' NOSUPERUSER NOBYPASSRLS;
          END IF;
          IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ar_platform') THEN
            CREATE ROLE ar_platform LOGIN PASSWORD 'ar_platform' NOSUPERUSER BYPASSRLS;
          END IF;
          IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ar_readonly') THEN
            CREATE ROLE ar_readonly LOGIN PASSWORD 'ar_readonly' NOSUPERUSER NOBYPASSRLS;
          END IF;
        END $$;
        """
    )
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gin")
    op.execute(
        """
        CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
          NEW.updated_at := now();
          RETURN NEW;
        END $$;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION app_tenant_id() RETURNS uuid
        LANGUAGE sql STABLE AS $$
          SELECT nullif(current_setting('app.tenant_id', true), '')::uuid
        $$;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION app_user_id() RETURNS uuid
        LANGUAGE sql STABLE AS $$
          SELECT nullif(current_setting('app.user_id', true), '')::uuid
        $$;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION forbid_update_delete() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
          RAISE EXCEPTION '% is append-only', TG_TABLE_NAME;
        END $$;
        """
    )
    op.execute("GRANT USAGE ON SCHEMA public TO ar_app, ar_platform, ar_readonly")
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO ar_app, ar_platform"
    )
    op.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO ar_readonly")


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS forbid_update_delete()")
    op.execute("DROP FUNCTION IF EXISTS app_user_id()")
    op.execute("DROP FUNCTION IF EXISTS app_tenant_id()")
    op.execute("DROP FUNCTION IF EXISTS set_updated_at()")
    op.execute("DROP EXTENSION IF EXISTS btree_gin")
    op.execute("DROP EXTENSION IF EXISTS vector")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
    op.execute("DROP EXTENSION IF EXISTS citext")
    op.execute("DROP EXTENSION IF EXISTS pgcrypto")

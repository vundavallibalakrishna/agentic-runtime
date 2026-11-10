"""Stage 11: usage keys, memory scope, tokens, and the records-table move.

Revision ID: 0040
Revises: 0039
Create Date: 2026-11-10

Expand, backfill, then contract.

* ``usage_events.api_key_id`` records which key spent the tokens.
* ``usage_daily`` gains ``api_key_id`` on its primary key. Existing rows use the
  zero uuid, so a day that had no key stays one row.
* Quotas may name an API key. Memory may be scoped to the workspace.
* ``file_blobs`` is copied into ``files`` plus ``file_blob_payloads``, then dropped.
* ``tool_versions.embedding`` is dropped. Nothing has read it since revision 0034.
* The records-product tables move to schema ``records_pack``. Guest tables stay.
  Downgrade moves the tables back and recreates the dropped column and blob table.
"""

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

from ar_domain.migrations.helpers import (
    add_updated_at_trigger,
    enable_tenant_rls,
    grant_tables,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0040"
down_revision: str | None = "0039"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ZERO = "00000000-0000-0000-0000-000000000000"
_RECORDS = (
    "evidence_custody_events",
    "legal_hold_members",
    "disposition_certificates",
    "binder_exports",
    "run_record_replays",
    "evidence_items",
    "legal_holds",
    "retention_schedules",
    "run_records",
    "agent_cards",
    "ai_incidents",
    "ai_oversight_daily",
)


def upgrade() -> None:
    op.execute("ALTER TABLE usage_events ADD COLUMN api_key_id uuid")
    op.execute(
        "CREATE INDEX ix_usage_events_api_key ON usage_events (tenant_id, api_key_id) "
        "WHERE api_key_id IS NOT NULL"
    )
    op.execute(
        f"ALTER TABLE usage_daily ADD COLUMN api_key_id uuid NOT NULL DEFAULT '{_ZERO}'::uuid"
    )
    op.execute("ALTER TABLE usage_daily DROP CONSTRAINT pk_usage_daily")
    op.execute(
        "ALTER TABLE usage_daily ADD CONSTRAINT pk_usage_daily PRIMARY KEY ("
        "tenant_id, day, metric, user_id, team_id, agent_id, model_alias, api_key_id)"
    )
    op.execute("ALTER TABLE quotas DROP CONSTRAINT IF EXISTS ck_quotas_scope_type")
    op.execute(
        "ALTER TABLE quotas ADD CONSTRAINT ck_quotas_scope_type CHECK "
        "(scope_type IN ('tenant','team','user','agent','api_key'))"
    )
    op.execute("ALTER TABLE memory_facts DROP CONSTRAINT IF EXISTS ck_memory_facts_scope")
    op.execute("ALTER TABLE memory_facts DROP CONSTRAINT IF EXISTS ck_memory_facts_scope_shape")
    op.execute(
        "ALTER TABLE memory_facts ADD CONSTRAINT ck_memory_facts_scope CHECK "
        "(scope IN ('user','agent','team','agent_user','workspace'))"
    )
    op.execute(
        "ALTER TABLE memory_facts ADD CONSTRAINT ck_memory_facts_scope_shape CHECK ("
        "(scope = 'user' AND user_id IS NOT NULL) "
        "OR (scope = 'agent' AND agent_id IS NOT NULL) "
        "OR (scope = 'team' AND team_id IS NOT NULL) "
        "OR (scope = 'agent_user' AND agent_id IS NOT NULL AND user_id IS NOT NULL) "
        "OR (scope = 'workspace'))"
    )
    _backfill_blobs()
    op.execute("DROP INDEX IF EXISTS ix_tool_versions_embedding")
    op.execute("ALTER TABLE tool_versions DROP COLUMN IF EXISTS embedding")
    _move_records("public", "records_pack")
    _password_and_push()


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS push_subscriptions")
    op.execute("DROP TABLE IF EXISTS password_resets")
    _move_records("records_pack", "public")
    op.execute("DROP SCHEMA IF EXISTS records_pack")
    op.execute("ALTER TABLE tool_versions ADD COLUMN embedding vector(1024)")
    op.execute(
        "CREATE INDEX ix_tool_versions_embedding ON tool_versions "
        "USING hnsw (embedding vector_cosine_ops)"
    )
    _restore_blobs()
    op.execute("ALTER TABLE memory_facts DROP CONSTRAINT IF EXISTS ck_memory_facts_scope_shape")
    op.execute("ALTER TABLE memory_facts DROP CONSTRAINT IF EXISTS ck_memory_facts_scope")
    op.execute(
        "ALTER TABLE memory_facts ADD CONSTRAINT ck_memory_facts_scope CHECK "
        "(scope IN ('user','agent','team','agent_user'))"
    )
    op.execute(
        "ALTER TABLE memory_facts ADD CONSTRAINT ck_memory_facts_scope_shape CHECK ("
        "(scope = 'user' AND user_id IS NOT NULL) "
        "OR (scope = 'agent' AND agent_id IS NOT NULL) "
        "OR (scope = 'team' AND team_id IS NOT NULL) "
        "OR (scope = 'agent_user' AND agent_id IS NOT NULL AND user_id IS NOT NULL))"
    )
    op.execute("DELETE FROM quotas WHERE scope_type = 'api_key'")
    op.execute("ALTER TABLE quotas DROP CONSTRAINT IF EXISTS ck_quotas_scope_type")
    op.execute(
        "ALTER TABLE quotas ADD CONSTRAINT ck_quotas_scope_type CHECK "
        "(scope_type IN ('tenant','team','user','agent'))"
    )
    op.execute("ALTER TABLE usage_daily DROP CONSTRAINT pk_usage_daily")
    op.execute("ALTER TABLE usage_daily DROP COLUMN api_key_id")
    op.execute(
        "ALTER TABLE usage_daily ADD CONSTRAINT pk_usage_daily PRIMARY KEY ("
        "tenant_id, day, metric, user_id, team_id, agent_id, model_alias)"
    )
    op.execute("DROP INDEX IF EXISTS ix_usage_events_api_key")
    op.execute("ALTER TABLE usage_events DROP COLUMN api_key_id")


def _password_and_push() -> None:
    op.create_table(
        "password_resets",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_password_resets_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_password_resets_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_password_resets")),
    )
    op.create_table(
        "push_subscriptions",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("endpoint", sa.Text(), nullable=False),
        sa.Column(
            "content_encoding", sa.Text(), server_default=sa.text("'aes128gcm'"), nullable=False
        ),
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
            name=op.f("fk_push_subscriptions_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_push_subscriptions_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_push_subscriptions")),
        sa.UniqueConstraint("tenant_id", "endpoint", name=op.f("uq_push_subscriptions_endpoint")),
    )
    add_updated_at_trigger("push_subscriptions")
    enable_tenant_rls("password_resets")
    enable_tenant_rls("push_subscriptions")
    grant_tables(["password_resets", "push_subscriptions"])


def _backfill_blobs() -> None:
    op.execute(
        """
        INSERT INTO files (
            id, tenant_id, owner_user_id, conversation_id, run_id, kind, name, mime_type,
            size_bytes, sha256, object_key, classification, status, scan_status, preview
        )
        SELECT
            b.id,
            b.tenant_id,
            CASE WHEN b.owner_user_id IN (SELECT id FROM users) THEN b.owner_user_id END,
            CASE WHEN b.conversation_id IN (SELECT id FROM conversations)
                THEN b.conversation_id END,
            CASE WHEN b.run_id IN (SELECT id FROM runs) THEN b.run_id END,
            CASE WHEN b.kind IN (
                'upload','artifact','tool_result','sandbox_snapshot','knowledge_raw',
                'knowledge_parsed','skill_asset','avatar','export','openapi_spec',
                'eval_dataset','event_payload'
            ) THEN b.kind ELSE 'upload' END,
            b.name,
            b.mime_type,
            b.size_bytes,
            NULLIF(b.sha256, ''),
            'legacy/file-blobs/' || b.id::text,
            'internal',
            'ready',
            'skipped',
            '{{}}'::jsonb
        FROM file_blobs b
        WHERE NOT EXISTS (SELECT 1 FROM files f WHERE f.id = b.id)
        """
    )
    op.create_table(
        "file_blob_payloads",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("body", sa.LargeBinary(), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_file_blob_payloads_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_file_blob_payloads")),
    )
    op.execute(
        """
        INSERT INTO file_blob_payloads (id, tenant_id, body)
        SELECT id, tenant_id, body FROM file_blobs
        """
    )
    op.execute("CREATE INDEX ix_file_blob_payloads_tenant ON file_blob_payloads (tenant_id)")
    enable_tenant_rls("file_blob_payloads")
    grant_tables(["file_blob_payloads"])
    op.execute("DROP TABLE file_blobs")


def _restore_blobs() -> None:
    op.execute(
        """
        CREATE TABLE file_blobs (
            id uuid PRIMARY KEY,
            tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            owner_user_id uuid,
            conversation_id uuid,
            run_id uuid,
            name text NOT NULL,
            mime_type text NOT NULL,
            sha256 text NOT NULL DEFAULT '',
            size_bytes bigint NOT NULL DEFAULT 0,
            kind text NOT NULL DEFAULT 'upload',
            body bytea NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        INSERT INTO file_blobs (
            id, tenant_id, owner_user_id, conversation_id, run_id, name, mime_type,
            sha256, size_bytes, kind, body
        )
        SELECT
            p.id, p.tenant_id, f.owner_user_id, f.conversation_id, f.run_id,
            COALESCE(f.name, 'file'), COALESCE(f.mime_type, 'application/octet-stream'),
            COALESCE(f.sha256, ''), COALESCE(f.size_bytes, octet_length(p.body)),
            COALESCE(f.kind, 'upload'), p.body
        FROM file_blob_payloads p
        LEFT JOIN files f ON f.id = p.id
        """
    )
    op.execute("CREATE INDEX ix_file_blobs_tenant ON file_blobs (tenant_id)")
    enable_tenant_rls("file_blobs")
    grant_tables(["file_blobs"])
    op.execute("DROP TABLE file_blob_payloads")


def _move_records(source: str, target: str) -> None:
    if target != "public":
        op.execute(f"CREATE SCHEMA IF NOT EXISTS {target}")
        op.execute(f"GRANT USAGE ON SCHEMA {target} TO ar_app, ar_platform, ar_readonly")
    for name in _RECORDS:
        op.execute(
            f"""
            DO $$
            BEGIN
                IF to_regclass('{source}.{name}') IS NOT NULL THEN
                    ALTER TABLE {source}.{name} SET SCHEMA {target};
                END IF;
            END $$;
            """
        )

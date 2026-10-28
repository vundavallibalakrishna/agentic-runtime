"""Process settings. Spec: docs/07-ops/environments.md sections 2-3."""

import os
from enum import StrEnum
from pathlib import Path

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from ar_common.host_ports import apply_host_ports

# Every name in docs/07-ops/environments.md §3. A variable outside this set is a typo.
CATALOGUE_ENV: frozenset[str] = frozenset(
    {
        "AR_API_INTERNAL_URL",
        "AR_ASGI_SERVER",
        "AR_AUDIT_ARCHIVE_BUCKET",
        "AR_BINDER_MAX_ITEMS",
        "AR_BILLING_CURRENCY",
        "AR_BOOTSTRAP_ADMIN_EMAIL",
        "AR_BOOTSTRAP_TENANT_NAME",
        "AR_BOOTSTRAP_TENANT_SLUG",
        "AR_CHANNELS_EMAIL_POLL_S",
        "AR_CHANNELS_PORT",
        "AR_CHANNELS_SLACK_UPDATE_INTERVAL_MS",
        "AR_CHANNELS_TEAMS_UPDATE_INTERVAL_MS",
        "AR_CHANNEL_LINK_TTL_S",
        "AR_CLAMAV_ADDRESS",
        "AR_CONSECUTIVE_TOOL_ERROR_LIMIT",
        "AR_CURSOR_SECRET",
        "AR_DATABASE_URL",
        "AR_DB_ENCRYPTION_ACTIVE_KEY",
        "AR_DB_ENCRYPTION_KEYS",
        "AR_DURABLE_STATE",
        "AR_DEV_MODEL_API_KEY",
        "AR_DEV_MODEL_BASE_URL",
        "AR_DELTA_COALESCE_MS",
        "AR_DEPLOYMENT_MODE",
        "AR_EGRESS_DENY_CIDRS",
        "AR_EGRESS_PROXY_URL",
        "AR_ENV",
        "AR_EVAL_CONCURRENCY",
        "AR_EVIDENCE_BUCKET",
        "AR_EVIDENCE_DEFAULT_LOCK_DAYS",
        "AR_EVIDENCE_LOCK_MODE",
        "AR_EVIDENCE_SIGNING_KEY",
        "AR_EVIDENCE_SIGNING_KEY_ID",
        "AR_FASTEMBED_CACHE_DIR",
        "AR_FILES_PROXY_DOWNLOADS",
        "AR_FILES_SCANNER",
        "AR_GRC_CONNECTOR_MAX_PAGES",
        "AR_GROUNDING_MAX_SENTENCES",
        "AR_GUARDRAIL_INPUT_ALIAS",
        "AR_GUARDRAIL_OUTPUT_ALIAS",
        "AR_GUEST_MAGIC_LINK_TTL_S",
        "AR_GUEST_MAX_TTL_DAYS",
        "AR_GUEST_SESSION_TTL_S",
        "AR_INGEST_ACTIVITY_CONCURRENCY",
        "AR_INGEST_MAX_BYTES",
        "AR_INGEST_SYNC_CONCURRENCY",
        "AR_INJECTION_CLASSIFIER_TIMEOUT_MS",
        "AR_INPUT_WAIT_TIMEOUT_S",
        "AR_INTERNAL_JWT_JWKS",
        "AR_INTERNAL_JWT_PRIVATE_KEY",
        "AR_KNOWLEDGE_RERANK_CANDIDATES",
        "AR_LOG_HASH_USER_IDS",
        "AR_MAX_DEPTH",
        "AR_MAX_JSON_BODY_BYTES",
        "AR_MAX_MESSAGE_CHARS",
        "AR_MCPG_PORT",
        "AR_MCP_GATEWAY_URL",
        "AR_MCP_INTERNAL_HTTP_ALLOWED_CIDRS",
        "AR_MCP_OPENAPI_URL",
        "AR_MCP_SQL_URL",
        "AR_MEMORY_DEDUPE_SIM",
        "AR_MEMORY_RECALL_MIN_SIM",
        "AR_MG_CB_FAILURES",
        "AR_MG_CB_OPEN_S",
        "AR_MG_HEALTH_INTERVAL_S",
        "AR_MG_MAX_FALLBACKS",
        "AR_MG_PORT",
        "AR_MG_SEMAPHORE_WAIT_S",
        "AR_MODEL_GATEWAY_URL",
        "AR_MODEL_PROVIDER_DENY_CIDRS",
        "AR_OFFLINE_SESSION_MAX_DAYS",
        "AR_OIDC_API_AUDIENCE",
        "AR_OIDC_CLIENT_ID",
        "AR_OIDC_CLIENT_SECRET",
        "AR_OIDC_ISSUER",
        "AR_OPA_BUNDLE_TOKEN",
        "AR_OPA_TIMEOUT_MS",
        "AR_OPA_URL",
        "AR_OTEL_EXPORTER_OTLP_ENDPOINT",
        "AR_OUTBOX_BATCH_SIZE",
        "AR_PACK_SIGNATURE_REQUIRED",
        "AR_PACK_TRUSTED_KEYS",
        "AR_PACKS_DIR",
        "AR_PGVECTOR_DIMENSIONS",
        "AR_PUBLIC_URL",
        "AR_QDRANT_API_KEY",
        "AR_QDRANT_URL",
        "AR_RETENTION_SWEEP_CRON",
        "AR_ROUTINE_MIN_INTERVAL_S",
        "AR_RUNTIME_MAX_CONCURRENT_ACTIVITIES",
        "AR_RUNTIME_MAX_CONCURRENT_WORKFLOW_TASKS",
        "AR_RUNTIME_TENANT_MAX_ACTIVE_RUNS",
        "AR_RUN_RECORD_MAX_BLOB_BYTES",
        "AR_RUN_STREAM_TTL_S",
        "AR_S3_ACCESS_KEY_ID",
        "AR_S3_BUCKET",
        "AR_S3_ENDPOINT",
        "AR_S3_PRESIGN_TTL_S",
        "AR_S3_PUBLIC_ENDPOINT",
        "AR_S3_REGION",
        "AR_S3_SECRET_ACCESS_KEY",
        "AR_S3_SSE",
        "AR_SAAS_SELF_SIGNUP",
        "AR_SANDBOX_ALLOWED_REGISTRIES",
        "AR_SANDBOX_DEFAULT_RUNTIME_CLASS",
        "AR_SANDBOX_DOCKER_RUNTIME",
        "AR_SANDBOX_DRIVER",
        "AR_SANDBOX_ENSURE_TIMEOUT_S",
        "AR_SANDBOX_MANAGER_URL",
        "AR_SANDBOX_MAX_PER_TENANT",
        "AR_SANDBOX_NAMESPACE",
        "AR_SANDBOX_PACKAGE_MIRRORS",
        "AR_SANDBOX_SNAPSHOT_INTERVAL_S",
        "AR_SANDBOX_WARM_POOL",
        "AR_SECRETS_BACKEND",
        "AR_SECRET_CACHE_TTL_S",
        "AR_SESSION_ENCRYPTION_KEY",
        "AR_SESSION_ENCRYPTION_KEY_PREVIOUS",
        "AR_SESSION_MAX_AGE_S",
        "AR_SESSION_TTL_S",
        "AR_SMTP_FROM",
        "AR_SMTP_HOST",
        "AR_SMTP_PASSWORD",
        "AR_SMTP_PORT",
        "AR_SMTP_STARTTLS",
        "AR_SMTP_USERNAME",
        "AR_SSE_MAX_PER_USER",
        "AR_STEP_UP_TTL_S",
        "AR_TEMPORAL_ADDRESS",
        "AR_TEMPORAL_NAMESPACE",
        "AR_TENANT_DB_ROUTES",
        "AR_TENANT_DELETE_GRACE_DAYS",
        "AR_TENANT_TEMPORAL_NAMESPACES",
        "AR_TOKEN_CACHE_KEY",
        "AR_TOOL_DRIFT_INTERVAL",
        "AR_TOOL_RESULT_MAX_FILE_BYTES",
        "AR_TRACE_SAMPLE_RATIO",
        "AR_TSA_TIMEOUT_MS",
        "AR_TSA_URL",
        "AR_TRACE_UI_URL",
        "AR_USAGE_ROLLUP_INTERVAL",
        "AR_VALKEY_URL",
        "AR_VAULT_ADDR",
        "AR_VAULT_AUTH",
        "AR_VAULT_KV_MOUNT",
        "AR_VAULT_ROLE",
        "AR_VAULT_TOKEN",
        "AR_VECTOR_BACKEND",
        "AR_VECTOR_MIGRATION_RETAIN_HOURS",
        "AR_VECTOR_PG_EF_SEARCH",
        "AR_VECTOR_PG_READ_DSN",
        "AR_WEBHOOK_ALLOW_PRIVATE",
    }
) | frozenset(
    {
        "AR_CLICKHOUSE_HOST_PORT",
        "AR_CLAMAV_HOST_PORT",
        "AR_EGRESS_HOST_PORT",
        "AR_FAKE_LLM_HOST_PORT",
        "AR_GRAFANA_HOST_PORT",
        "AR_INGEST_HOST_PORT",
        "AR_KEYCLOAK_HOST_PORT",
        "AR_LANGFUSE_HOST_PORT",
        "AR_MAILPIT_UI_HOST_PORT",
        "AR_MCP_OPENAPI_HOST_PORT",
        "AR_MCP_SQL_HOST_PORT",
        "AR_OPA_HOST_PORT",
        "AR_OTEL_GRPC_HOST_PORT",
        "AR_OTEL_HTTP_HOST_PORT",
        "AR_PG_HOST_PORT",
        "AR_PORT",
        "AR_PROMETHEUS_HOST_PORT",
        "AR_QDRANT_GRPC_HOST_PORT",
        "AR_QDRANT_HTTP_HOST_PORT",
        "AR_RUNTIME_HOST_PORT",
        "AR_S3_HOST_PORT",
        "AR_SANDBOX_AGENT_HOST_PORT",
        "AR_SANDBOX_MANAGER_HOST_PORT",
        "AR_SYSTEM_HOST_PORT",
        "AR_TEMPO_HOST_PORT",
        "AR_TEMPORAL_HOST_PORT",
        "AR_TEMPORAL_UI_HOST_PORT",
        "AR_VALKEY_HOST_PORT",
        "AR_VAULT_HOST_PORT",
        "AR_WEB_HOST_PORT",
    }
)


class EnvName(StrEnum):
    DEV = "dev"
    CI = "ci"
    STAGING = "staging"
    PROD = "prod"


class DeploymentMode(StrEnum):
    SAAS = "saas"
    SINGLE_TENANT = "single_tenant"


class BaseServiceSettings(BaseSettings):
    """Settings shared by every deployable. Environment prefix is ``AR_``."""

    model_config = SettingsConfigDict(
        env_prefix="AR_",
        extra="ignore",
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
    )

    env: EnvName = EnvName.DEV
    deployment_mode: DeploymentMode = DeploymentMode.SINGLE_TENANT
    otel_exporter_otlp_endpoint: str = "http://localhost:4317"
    log_hash_user_ids: bool = False
    cursor_secret: SecretStr = SecretStr("dev-cursor-secret")
    max_json_body_bytes: int = 1_048_576
    trace_sample_ratio: float = Field(default=0.1, ge=0.0, le=1.0)
    valkey_url: str = "redis://localhost:6379/0"
    database_url: str = "postgresql+asyncpg://ar_app:ar_app@localhost:5432/agentic_runtime"
    model_gateway_url: str = ""
    temporal_address: str = ""
    temporal_namespace: str = ""
    s3_endpoint: str = "http://localhost:8333"
    s3_public_endpoint: str = "http://localhost:8333"
    s3_region: str = "us-east-1"
    s3_bucket: str = "ar-files"
    s3_access_key_id: str = ""
    s3_secret_access_key: SecretStr = SecretStr("")
    s3_presign_ttl_s: int = 300
    internal_jwt_private_key: SecretStr = SecretStr("")
    internal_jwt_jwks: str = ""
    secrets_backend: str = "db_encrypted"
    db_encryption_keys: SecretStr = SecretStr("")
    db_encryption_active_key: str = "k1"
    vault_addr: str = "http://localhost:8200"
    vault_token: SecretStr = SecretStr("")
    vault_kv_mount: str = "ar"
    asgi_server: str = "uvicorn"
    service_name: str = "agentic-runtime"
    routine_min_interval_s: int = 300
    binder_max_items: int = 5000
    evidence_bucket: str = "ar-evidence"
    evidence_default_lock_days: int = 2555
    evidence_lock_mode: str = "compliance"
    evidence_signing_key: SecretStr = SecretStr("")
    evidence_signing_key_id: str = "evidence-k1"
    grc_connector_max_pages: int = 50
    grounding_max_sentences: int = 200
    guest_magic_link_ttl_s: int = 900
    guest_max_ttl_days: int = 90
    guest_session_ttl_s: int = 28800
    pack_signature_required: bool = False
    pack_trusted_keys: SecretStr = SecretStr("")
    packs_dir: str = "packs"
    run_record_max_blob_bytes: int = 52_428_800
    tsa_timeout_ms: int = 2000
    tsa_url: str = ""
    guardrail_input_alias: str = "fast"
    guardrail_output_alias: str = "fast"
    injection_classifier_timeout_ms: int = 1000
    audit_archive_bucket: str = "ar-audit-archive"

    @model_validator(mode="after")
    def apply_file_secrets_and_saas_default(self) -> BaseServiceSettings:
        """Honour ``AR_*_FILE`` secrets and hash user ids by default in SaaS."""
        for env_name, attr in (
            ("CURSOR_SECRET", "cursor_secret"),
            ("INTERNAL_JWT_PRIVATE_KEY", "internal_jwt_private_key"),
            ("S3_SECRET_ACCESS_KEY", "s3_secret_access_key"),
        ):
            file_path = os.environ.get(f"AR_{env_name}_FILE")
            if file_path:
                setattr(self, attr, SecretStr(Path(file_path).read_text(encoding="utf-8").strip()))
        if self.deployment_mode is DeploymentMode.SAAS and "AR_LOG_HASH_USER_IDS" not in os.environ:
            self.log_hash_user_ids = True
        apply_host_ports(self)
        return self


class _SettingsState:
    current: BaseServiceSettings | None = None


def get_settings() -> BaseServiceSettings:
    """Return the process settings, loading them once."""
    if _SettingsState.current is None:
        _SettingsState.current = BaseServiceSettings()
    return _SettingsState.current


def set_settings(settings: BaseServiceSettings) -> None:
    """Replace the cached settings. Tests use this."""
    _SettingsState.current = settings


def unknown_env_names(settings: BaseServiceSettings | None = None) -> list[str]:
    """Return ``AR_*`` variables that are neither settings fields nor catalogue entries."""
    current = get_settings() if settings is None else settings
    known = {f"AR_{name.upper()}" for name in type(current).model_fields} | CATALOGUE_ENV
    return sorted(
        key
        for key in os.environ
        if key.startswith("AR_") and key not in known and not key.endswith("_FILE")
    )

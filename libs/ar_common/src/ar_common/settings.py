"""Process settings. Spec: docs/07-ops/environments.md sections 2-3."""

import hashlib
import ipaddress
import os
from enum import StrEnum
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from ar_common.host_ports import apply_host_ports

# Every name in docs/07-ops/environments.md §3. A variable outside this set is a typo.
CATALOGUE_ENV: frozenset[str] = frozenset(
    {
        "AR_API_INTERNAL_URL",
        "AR_APPROVAL_WAIT_S",
        "AR_ASGI_SERVER",
        "AR_AUTH_MODE",
        "AR_AUDIT_ARCHIVE_BUCKET",
        "AR_BINDER_MAX_ITEMS",
        "AR_BILLING_CURRENCY",
        "AR_BOOTSTRAP_ADMIN_EMAIL",
        "AR_BOOTSTRAP_TENANT_NAME",
        "AR_BOOTSTRAP_TENANT_SLUG",
        "AR_CA_BUNDLE",
        "AR_CHANNELS_EMAIL_POLL_S",
        "AR_CHANNELS_PORT",
        "AR_CHANNELS_SLACK_UPDATE_INTERVAL_MS",
        "AR_CHANNELS_TEAMS_UPDATE_INTERVAL_MS",
        "AR_CHANNEL_LINK_TTL_S",
        "AR_CLAMAV_ADDRESS",
        "AR_CLAMAV_TIMEOUT_S",
        "AR_CONSECUTIVE_TOOL_ERROR_LIMIT",
        "AR_CSRF_ALLOWED_ORIGINS",
        "AR_CURSOR_SECRET",
        "AR_DATA_RESIDENCY",
        "AR_DEFAULT_CONTEXT_WINDOW",
        "AR_DOCUMENT_ALIGN_COSINE",
        "AR_DOCUMENT_ALIGN_LEXICAL",
        "AR_DOCUMENT_CHUNK_CHARS",
        "AR_DOCUMENT_CROSSCHECK_MAX_CHARS",
        "AR_DOCUMENT_CHUNK_OVERLAP",
        "AR_DOCUMENT_COLLECTION_CAP",
        "AR_DOCUMENT_ASK_MAX_TOKENS",
        "AR_DOCUMENT_CREATE_MAX_BULLETS",
        "AR_DOCUMENT_CREATE_MAX_COLUMNS",
        "AR_DOCUMENT_CREATE_MAX_FILE_BYTES",
        "AR_DOCUMENT_CREATE_MAX_PAGES",
        "AR_DOCUMENT_CREATE_MAX_PARAGRAPHS",
        "AR_DOCUMENT_CREATE_MAX_ROWS",
        "AR_DOCUMENT_CREATE_MAX_SECTIONS",
        "AR_DOCUMENT_CREATE_MAX_SHEETS",
        "AR_DOCUMENT_CREATE_MAX_SLIDES",
        "AR_DOCUMENT_CREATE_MAX_TEXT",
        "AR_DOCUMENT_CREATE_MAX_TITLE",
        "AR_DOCUMENT_EXCERPT_CHARS",
        "AR_DOCUMENT_HEADING_CAP",
        "AR_DOCUMENT_HISTORY_RESERVE",
        "AR_DOCUMENT_INSTRUCTION_RESERVE",
        "AR_DOCUMENT_LISTED_ITEM_CAP",
        "AR_DOCUMENT_LOW_TEXT_CHARS",
        "AR_DOCUMENT_MARGIN_RATIO",
        "AR_DOCUMENT_MAX_BYTES",
        "AR_DOCUMENT_MAX_PAGES",
        "AR_DOCUMENT_OUTPUT_RESERVE",
        "AR_DOCUMENT_READ_CHARS",
        "AR_DOCUMENT_RETRIEVAL_BUDGET",
        "AR_DOCUMENT_SEARCH_DOCUMENT_CAP",
        "AR_DOCUMENT_SEARCH_HITS",
        "AR_DOCUMENT_SEARCH_SNIPPET_CHARS",
        "AR_DOCUMENT_SEARCH_TOP_K",
        "AR_DOCUMENT_SOURCE_REF_CHARS",
        "AR_DOCUMENT_SECTION_CAP",
        "AR_DOCUMENT_TABLE_MAX_ROWS",
        "AR_DOCUMENT_TABLE_PREVIEW_ROWS",
        "AR_DOCUMENT_TASK_PARALLELISM",
        "AR_DOCUMENT_TOKEN_FACTOR",
        "AR_DOCUMENT_TOOL_RESERVE",
        "AR_DOCUMENT_VISION_MAX_BYTES",
        "AR_DOCUMENT_ZIP_MEMBERS",
        "AR_FILE_EXPIRY_MAX_SECONDS",
        "AR_FILE_EXPIRY_MIN_SECONDS",
        "AR_DATABASE_URL",
        "AR_DB_APP_PASSWORD",
        "AR_DB_CERT_DIR",
        "AR_DB_CONNECT_DEADLINE_S",
        "AR_DB_ENCRYPTION_ACTIVE_KEY",
        "AR_DB_MAX_ADDRESSES",
        "AR_DB_MIN_SSLMODE",
        "AR_DB_OWNER_PASSWORD",
        "AR_DB_PLATFORM_PASSWORD",
        "AR_DB_READONLY_PASSWORD",
        "AR_DB_TEMPORAL_PASSWORD",
        "AR_DB_STRICT_TLS",
        "AR_DB_STRICT_TLS_FLOOR",
        "AR_DB_ENCRYPTION_KEYS",
        "AR_DURABLE_STATE",
        "AR_DEV_MODEL_API_KEY",
        "AR_DEV_MODEL_BASE_URL",
        "AR_DELTA_COALESCE_MS",
        "AR_DEPLOYMENT_MODE",
        "AR_EGRESS_ALLOW_LOOPBACK",
        "AR_EGRESS_ALLOW_NAMED_PRIVATE",
        "AR_EGRESS_ALLOW_WILDCARD",
        "AR_EGRESS_CLOSED",
        "AR_EGRESS_DENY_CIDRS",
        "AR_EGRESS_HOSTS",
        "AR_EGRESS_PROXY_URL",
        "AR_EMBEDDING_TIMEOUT_S",
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
        "AR_GROUNDING_MAX_SENTENCES",
        "AR_GUARDRAIL_INPUT_ALIAS",
        "AR_GUARDRAIL_OUTPUT_ALIAS",
        "AR_GUEST_MAGIC_LINK_TTL_S",
        "AR_GUEST_MAX_TTL_DAYS",
        "AR_GUEST_SESSION_TTL_S",
        "AR_INGEST_ACTIVITY_CONCURRENCY",
        "AR_INGEST_INLINE_MAX_BYTES",
        "AR_INGEST_MAX_BYTES",
        "AR_INGEST_SYNC_CONCURRENCY",
        "AR_INJECTION_CLASSIFIER_TIMEOUT_MS",
        "AR_INPUT_WAIT_TIMEOUT_S",
        "AR_INTERNAL_JWT_JWKS",
        "AR_INTERNAL_JWT_PRIVATE_KEY",
        "AR_KNOWLEDGE_FETCH_MAX_BYTES",
        "AR_KNOWLEDGE_RERANK_CANDIDATES",
        "AR_KNOWLEDGE_SEARCH_MAX_HITS",
        "AR_LOGIN_LOCKOUT_S",
        "AR_LOGIN_MAX_ATTEMPTS",
        "AR_LLM_MAX_TOKENS",
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
        "AR_MG_FALLBACK_BACKOFF_S",
        "AR_MG_MAX_FALLBACKS",
        "AR_MG_PORT",
        "AR_MG_SEMAPHORE_WAIT_S",
        "AR_MODEL_GATEWAY_URL",
        "AR_MODEL_PROVIDER_DENY_CIDRS",
        "AR_OIDC_AUDIENCE",
        "AR_OIDC_CLIENT_ID",
        "AR_OIDC_CLIENT_SECRET",
        "AR_OIDC_ISSUER",
        "AR_OIDC_JWKS_URL",
        "AR_OIDC_MFA_ACR",
        "AR_OIDC_MFA_AMR",
        "AR_OIDC_REDIRECT_URL",
        "AR_OIDC_REQUIRE_MFA",
        "AR_OPA_BUNDLE_TOKEN",
        "AR_OPA_TIMEOUT_MS",
        "AR_OPA_URL",
        "AR_OTEL_EXPORTER_OTLP_ENDPOINT",
        "AR_PLATFORM_DB_DENY_CIDRS",
        "AR_PLATFORM_DB_DENY_HOSTS",
        "AR_OUTBOX_BATCH_SIZE",
        "AR_PASSWORD_LOGIN",
        "AR_PASSWORD_MFA",
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
        "AR_RUN_HISTORY_STEPS",
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
        "AR_SEARCH_API_KEY",
        "AR_SEARCH_BASE_URL",
        "AR_SEARCH_PROVIDER",
        "AR_SANDBOX_ALLOW_UNISOLATED",
        "AR_SANDBOX_ALLOWED_REGISTRIES",
        "AR_SANDBOX_DOCKER_NETWORK",
        "AR_SANDBOX_DOCKER_RUNTIME",
        "AR_SANDBOX_DRIVER",
        "AR_SANDBOX_EGRESS_PROXY",
        "AR_SANDBOX_ENSURE_TIMEOUT_S",
        "AR_SANDBOX_MANAGER_URL",
        "AR_SANDBOX_MAX_PER_TENANT",
        "AR_SANDBOX_PACKAGE_MIRRORS",
        "AR_SANDBOX_SNAPSHOT_INTERVAL_S",
        "AR_SANDBOX_WARM_POOL",
        "AR_SECRETS_BACKEND",
        "AR_SECRET_CACHE_TTL_S",
        "AR_SESSION_ENCRYPTION_KEY",
        "AR_SESSION_ENCRYPTION_KEY_PREVIOUS",
        "AR_SESSION_GATE_TTL_S",
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
        "AR_TEMPORAL_NUM_HISTORY_SHARDS",
        "AR_TENANT_DB_ROUTES",
        "AR_TENANT_DELETE_GRACE_DAYS",
        "AR_TENANT_TEMPORAL_NAMESPACES",
        "AR_TOKEN_CACHE_KEY",
        "AR_TOOL_DRIFT_INTERVAL",
        "AR_TOOL_RESULT_MAX_FILE_BYTES",
        "AR_TOOL_WORKER_THREADS",
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
        "AR_GRAFANA_HOST_PORT",
        "AR_INGEST_HOST_PORT",
        "AR_LANGFUSE_HOST_PORT",
        "AR_MAILPIT_UI_HOST_PORT",
        "AR_MCP_OPENAPI_HOST_PORT",
        "AR_MCP_SQL_HOST_PORT",
        "AR_OPA_HOST_PORT",
        "AR_OTEL_GRPC_HOST_PORT",
        "AR_OTEL_HTTP_HOST_PORT",
        "AR_PG_HOST_PORT",
        "AR_PII_LANGUAGE_MODEL",
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


def fake_models_allowed(env: EnvName) -> bool:
    """Fake models, scripted turns and demo fixtures exist only in dev and CI."""
    return env in {EnvName.DEV, EnvName.CI}


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
    # Whether a tool, a connector or a model provider may reach this machine's own
    # addresses (127.0.0.0/8, localhost). An install decides; the default is no.
    egress_allow_loopback: bool = False
    # Whether ``*`` (reach any host) is honoured in a sandbox egress allowlist. An install
    # decides; the default is no, so an allowlist must name its hosts.
    egress_allow_wildcard: bool = False
    # When true, model calls, embeddings, connectors, knowledge fetches, search,
    # webhooks and telemetry may only dial a host on the tenant allowlist or
    # AR_EGRESS_HOSTS. Default false, so an existing cloud provider keeps working.
    # The air-gap Helm overlay turns it on.
    egress_closed: bool = False
    # Comma-separated hosts this install may reach even when a tenant list is empty.
    # Used for in-cluster names such as otel-collector when egress_closed is on.
    egress_hosts: str = ""
    # Off by default. An exact allowlist name may resolve to a private address only
    # when this is true. The air-gap overlay turns it on. Metadata addresses stay denied.
    egress_allow_named_private: bool = False
    # Extra trust anchor for outbound TLS. ``SSL_CERT_FILE`` wins when this is empty.
    ca_bundle: str = ""
    # Directory customer-database TLS files must live under. Client certificates
    # and keys are read only from ``<dir>/<tenant id>/``. Empty refuses client
    # certificates. ``sslrootcert=system`` and the ``AR_CA_BUNDLE`` file stay allowed.
    db_cert_dir: str = ""
    # How many resolved addresses a customer database dial will try.
    db_max_addresses: int = 4
    # Overall budget, in seconds, for those attempts.
    db_connect_deadline_s: float = 15
    # Lowest libpq sslmode a customer database may use. Empty means no floor,
    # except closed egress. With ``db_strict_tls``, closed egress requires
    # ``verify-full``. With it off, closed egress requires ``require``.
    db_min_sslmode: str = ""
    # When true, closed egress rejects ``require`` and demands certificate verification.
    db_strict_tls: bool = True
    # ``verify-full`` checks the server name. Set ``verify-ca`` for a database
    # addressed by IP, or whose certificate has no matching name.
    db_strict_tls_floor: str = "verify-full"
    # Comma-separated names of the platform database services. A customer DSN that
    # resolves to one of them is refused on any port.
    platform_db_deny_hosts: str = ""
    # Comma-separated CIDRs of the platform database pods.
    platform_db_deny_cidrs: str = ""
    # Empty leaves each tenant's data_residency column in charge. ``cluster`` forces
    # model and embedding URLs onto a private or loopback address for the whole install.
    data_residency: str = ""
    # Install-wide SearXNG address. A tenant search.baseUrl wins. Empty means none.
    search_base_url: str = ""
    # Whether a sandbox may run without kernel isolation (the docker driver, or an empty
    # one that runs on the host). An install decides; the default is no.
    sandbox_allow_unisolated: bool = False
    # Names this install on a container host it may share. Empty derives it from the
    # database address, which is what makes two installs different.
    install_id: str = ""
    # How often idle computers are suspended, expired ones ended and orphans removed.
    sandbox_reap_interval_s: int = Field(default=60, ge=1)
    # A container or folder younger than this is never treated as an orphan: its row may
    # not be saved yet.
    sandbox_orphan_grace_s: int = Field(default=120, ge=0)
    # The largest compressed workspace a suspend keeps. A larger one stays running.
    sandbox_snapshot_max_mb: int = Field(default=256, ge=1)
    # How long one process may hold a computer's scope while it starts, suspends or
    # resumes it. Another process waits up to ``AR_SANDBOX_ENSURE_TIMEOUT_S`` for it.
    sandbox_lock_ttl_s: int = Field(default=300, ge=1)
    # The most rows of one table file the table tools read. A longer file is refused,
    # never read in part. Each row is held in the query engine while a statement runs.
    table_max_rows: int = Field(default=1_000_000, ge=1)
    # How often a worker reports a running activity to Temporal, at most. A stop reaches
    # an activity with that report, so this is how long a reply keeps being written after
    # a person presses Stop. Temporal's own default is 0.8 of the heartbeat timeout.
    activity_heartbeat_throttle_s: int = Field(default=2, ge=1, le=60)
    sandbox_ensure_timeout_s: int = Field(default=30, ge=1)
    # The mail server the product sends through: invitations, and a routine's result when
    # its delivery names no email integration. An empty host means no mail is sent.
    smtp_host: str = ""
    smtp_port: int = 1025
    smtp_from: str = "noreply@dev.local"
    smtp_starttls: bool = False
    smtp_username: str = ""
    smtp_password: SecretStr = SecretStr("")
    # The scanner the product runs over every upload: ``clamav`` or ``none``. An install
    # decides; the default scans. ``none`` is set where no scanner is deployed.
    files_scanner: str = "clamav"
    # clamd ``host:port`` or a unix socket path. Empty with ``files_scanner=clamav``
    # rejects the upload: a named scanner that cannot be reached is not a clean file.
    clamav_address: str = ""
    clamav_timeout_s: float = Field(default=10, ge=1, le=120)
    # How many section readings one document task runs at once, and how many it
    # will run at all. One GPU on one node is the reason the default is 2.
    document_task_parallelism: int = Field(default=2, ge=1, le=8)
    document_section_cap: int = Field(default=200, ge=1, le=500)
    document_output_reserve: int = Field(default=4096, ge=0)
    document_instruction_reserve: int = Field(default=2000, ge=0)
    document_tool_reserve: int = Field(default=1500, ge=0)
    document_history_reserve: int = Field(default=500, ge=0)
    document_margin_ratio: float = Field(default=0.15, ge=0, le=0.5)
    document_align_lexical: float = Field(default=0.5, ge=0, le=1)
    document_align_cosine: float = Field(default=0.75, ge=0, le=1)
    # Outline entries returned in one page. The next page is a cursor, not a silent cut.
    document_heading_cap: int = Field(default=15, ge=1)
    document_token_factor: float = Field(default=1.15, ge=1, le=3)
    document_low_text_chars: int = Field(default=40, ge=1)
    # A file over this size or page count is refused with the count. Result sets page.
    document_max_bytes: int = Field(default=25 * 1024 * 1024, ge=1)
    document_max_pages: int = Field(default=600, ge=1)
    document_read_chars: int = Field(default=12_000, ge=1)
    document_retrieval_budget: int = Field(default=12_000, ge=1)
    document_chunk_chars: int = Field(default=1000, ge=1)
    document_chunk_overlap: int = Field(default=120, ge=0)
    document_excerpt_chars: int = Field(default=1500, ge=1)
    document_search_hits: int = Field(default=30, ge=1)
    document_search_snippet_chars: int = Field(default=240, ge=1)
    document_search_top_k: int = Field(default=8, ge=1)
    document_search_document_cap: int = Field(default=50, ge=1)
    # Collections named on one search call. Further collections come back as a cursor.
    document_collection_cap: int = Field(default=20, ge=1)
    document_table_preview_rows: int = Field(default=8, ge=1)
    document_table_max_rows: int = Field(default=2000, ge=1)
    document_zip_members: int = Field(default=30, ge=1)
    # Compaction uses the registered model window. This is the fallback when none is registered.
    default_context_window: int = Field(default=8000, ge=1)
    document_create_max_sections: int = Field(default=40, ge=1)
    document_create_max_sheets: int = Field(default=12, ge=1)
    document_create_max_rows: int = Field(default=500, ge=1)
    document_create_max_columns: int = Field(default=32, ge=1)
    document_create_max_paragraphs: int = Field(default=40, ge=1)
    document_create_max_bullets: int = Field(default=40, ge=1)
    document_create_max_text: int = Field(default=4000, ge=1)
    document_create_max_title: int = Field(default=200, ge=1)
    document_create_max_file_bytes: int = Field(default=5_242_880, ge=1)
    document_create_max_pages: int = Field(default=30, ge=1)
    document_create_max_slides: int = Field(default=60, ge=1)
    document_source_ref_chars: int = Field(default=500, ge=1)
    document_crosscheck_max_chars: int = Field(default=40_000, ge=1)
    document_vision_max_bytes: int = Field(default=8 * 1024 * 1024, ge=1)
    document_ask_max_tokens: int = Field(default=1800, ge=1)
    document_listed_item_cap: int = Field(default=40, ge=1)
    ingest_max_bytes: int = Field(default=209_715_200, ge=1)
    ingest_inline_max_bytes: int = Field(default=256 * 1024, ge=1)
    knowledge_fetch_max_bytes: int = Field(default=2_000_000, ge=1)
    knowledge_search_max_hits: int = Field(default=20, ge=1)
    # ``expiresAfterSeconds`` on an upload. The bounds match the Files API.
    file_expiry_min_seconds: int = Field(default=3600, ge=1)
    file_expiry_max_seconds: int = Field(default=2_592_000, ge=1)
    # Empty means the only tenant in the database (a single-tenant install has one).
    bootstrap_tenant_slug: str = ""
    otel_exporter_otlp_endpoint: str = ""
    # Shared HMAC secret for sandbox-manager, mcp-gateway, and /metrics.
    # Empty fails closed: those routes reject every call.
    internal_auth_secret: SecretStr = SecretStr("")
    # Chat retrieval drops chunks below this score (rerank or dense similarity).
    # Unset: the rerank model's own floor when a reranker is configured, and no
    # numeric bar when it is not.
    knowledge_min_score: float | None = Field(default=None, ge=0.0, le=1.0)
    log_hash_user_ids: bool = False
    cursor_secret: SecretStr = SecretStr("dev-cursor-secret")
    max_json_body_bytes: int = 1_048_576
    trace_sample_ratio: float = Field(default=0.1, ge=0.0, le=1.0)
    valkey_url: str = "redis://localhost:6379/0"
    database_url: str = "postgresql+asyncpg://ar_app@localhost:5432/agentic_runtime"
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
    grounding_max_sentences: int = 200
    guest_magic_link_ttl_s: int = 900
    guest_max_ttl_days: int = 90
    guest_session_ttl_s: int = 28800
    pack_signature_required: bool = False
    pack_trusted_keys: SecretStr = SecretStr("")
    packs_dir: str = "packs"
    run_record_max_blob_bytes: int = 52_428_800
    # Activities one workflow execution records before continue-as-new. The run's
    # own budget (``max_steps``) is still the cap on work.
    run_history_steps: int = Field(default=24, ge=1)
    # How long a run waits for an approval or a person's answer. A tenant can
    # pass a shorter ``wait_s`` on the workflow payload; this is the install default.
    approval_wait_s: int = Field(default=86400, ge=1)
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
        self._refuse_default_cursor_secret()
        self._refuse_bad_platform_cidrs()
        return self

    def _refuse_bad_platform_cidrs(self) -> None:
        """A malformed deny CIDR stops the process instead of being skipped."""
        floor = self.db_strict_tls_floor.strip().lower()
        if floor not in {"verify-ca", "verify-full"}:
            raise ValueError("AR_DB_STRICT_TLS_FLOOR must be verify-ca or verify-full")
        self.db_strict_tls_floor = floor
        for raw in self.platform_db_deny_cidrs.split(","):
            text = raw.strip()
            if not text:
                continue
            try:
                ipaddress.ip_network(text, strict=False)
            except ValueError as exc:
                raise ValueError(f"AR_PLATFORM_DB_DENY_CIDRS has an invalid CIDR: {text}") from exc

    def _refuse_default_cursor_secret(self) -> None:
        """Staging and production do not boot with a missing or well-known cursor secret."""
        if self.env in {EnvName.DEV, EnvName.CI}:
            return
        secret = self.cursor_secret.get_secret_value().strip()
        if secret and secret != DEV_CURSOR_SECRET:
            return
        raise ValueError(
            "AR_CURSOR_SECRET must be set to a value other than the dev default "
            f"when AR_ENV is {self.env.value}"
        )


class _SettingsState:
    current: BaseServiceSettings | None = None


def loopback_allowed(settings: BaseServiceSettings | None = None) -> bool:
    """Whether a loopback address may be reached: ``AR_EGRESS_ALLOW_LOOPBACK``.

    Every process and every check asks here, so the API, the workers that run tool calls
    and the checks inside the tools apply one rule. It is a setting of the install, not a
    consequence of the environment's name.
    """
    return (settings or get_settings()).egress_allow_loopback


def wildcard_egress_allowed(settings: BaseServiceSettings | None = None) -> bool:
    """Whether ``*`` is honoured in a sandbox egress allowlist: ``AR_EGRESS_ALLOW_WILDCARD``.

    It is a setting of the install, not a consequence of the environment's name: a run
    that has not turned it on drops ``*`` from the allowlist, so an allowlist names hosts.
    """
    return (settings or get_settings()).egress_allow_wildcard


DEV_CURSOR_SECRET = "dev-cursor-secret"  # noqa: S105 - the value that must be refused


def host_exec_allowed(settings: BaseServiceSettings | None = None) -> bool:
    """Host bash is a development driver. Staging and production never run it."""
    current = get_settings() if settings is None else settings
    return current.env in {EnvName.DEV, EnvName.CI}


def uses_shared_process_state(env: EnvName) -> bool:
    """Sessions, idempotency and run events leave the process outside dev and CI."""
    return env not in {EnvName.DEV, EnvName.CI}


def cursor_secret_text() -> str:
    """The cursor HMAC secret. Outside dev and CI a missing or default value refuses."""
    raw = os.environ.get("AR_CURSOR_SECRET", "").strip()
    env = os.environ.get("AR_ENV", "dev").strip().lower()
    if env not in {"dev", "ci"} and (not raw or raw == DEV_CURSOR_SECRET):
        raise RuntimeError("AR_CURSOR_SECRET must be set to a value other than the dev default")
    return raw or DEV_CURSOR_SECRET


def unisolated_sandbox_allowed(settings: BaseServiceSettings | None = None) -> bool:
    """Whether a sandbox may run without kernel isolation: ``AR_SANDBOX_ALLOW_UNISOLATED``.

    It is a setting of the install, not a consequence of the environment's name: a run
    that has not turned it on refuses the docker driver and the host driver.
    """
    return (settings or get_settings()).sandbox_allow_unisolated


def install_id(settings: BaseServiceSettings | None = None) -> str:
    """The id of this install: ``AR_INSTALL_ID``, or one derived from the database address.

    Sandbox containers carry it as a label, and the sweep that removes orphans touches
    only containers with this id. Two installs that share a container host have different
    databases, so the derived id differs without anyone setting it.
    """
    current = settings or get_settings()
    named = current.install_id.strip()
    if named:
        return named
    parts = urlsplit(current.database_url)
    address = f"{parts.hostname or ''}:{parts.port or ''}{parts.path}"
    return hashlib.sha256(address.encode()).hexdigest()[:16]


def files_scanner_name(settings: BaseServiceSettings | None = None) -> str:
    """The scanner for every upload: ``AR_FILES_SCANNER`` (``clamav`` or ``none``).

    It is a setting of the install, not a consequence of the environment's name. The
    default scans; a run with no scanner deployed sets ``none``.
    """
    name = (settings or get_settings()).files_scanner.strip().lower()
    return name if name in {"clamav", "none"} else "clamav"


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

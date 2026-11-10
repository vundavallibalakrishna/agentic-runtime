"""Product chat behaviour. Specs 04-07 and 13.

``ChatService`` is the in-memory test double. Staging and production serve API
reads and writes from Postgres repositories, one transaction per request
(ADR-0033). Model calls use the model gateway when ``model_gateway_url`` is
set, and fake-llm otherwise. A connected Temporal client runs each turn on the
runtime worker.
"""

import asyncio
import contextlib
import hashlib
import re
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

import httpx

from ar_common.errors import ArError, ConflictError, ErrorCode, NotFoundError
from ar_common.host_ports import fake_llm_base_url
from ar_common.ids import new_id
from ar_common.logging import get_logger
from ar_common.sandboxkit import csv_rows, xlsx_rows
from ar_common.time import utcnow
from ar_domain.agents.access import Actor
from ar_domain.agents.logic import AgentView, assistant_definition, can_see_agent, can_start_run
from ar_domain.agents.service import AgentLifecycle
from ar_domain.conversations.logic import (
    MessageNode,
    activate_branch,
    run_is_active,
    run_is_working,
)
from ar_domain.demo_ids import demo_id as demo_id  # noqa: PLC0414
from ar_domain.files.logic import (
    FileView,
    can_read_file,
    object_key,
    scan_bytes,
    typed_by_name,
    upload_rules,
)
from ar_domain.identity.tenant_settings import settings_for
from ar_domain.models.aliases import default_params as default_alias_params
from ar_domain.models.logic import (
    DEFAULT_DENY_CIDRS,
    AliasRef,
    completion_text,
    provider_url_denied,
    resolve_alias,
    valid_alias,
)
from ar_domain.runs.failure import fail_run, reply_error
from ar_domain.runs.logic import budget_exceeded
from ar_domain.usage.logic import UsageRecord, gateway_dedupe_keys

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy.ext.asyncio import AsyncEngine

    from ar_domain.files.objects import ObjectStore


def _iso(value: datetime | None) -> str | None:
    return None if value is None else value.isoformat()


def _object_dict(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    return {str(key): item for key, item in value.items()}


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item) for item in value)


def _workflow_not_found(exc: BaseException) -> bool:
    """A missing workflow is a lost turn. Any other error is not."""
    try:
        from temporalio.service import RPCError, RPCStatusCode  # noqa: PLC0415
    except ImportError:
        return "NotFound" in type(exc).__name__
    return isinstance(exc, RPCError) and exc.status == RPCStatusCode.NOT_FOUND


def _seq(event: dict[str, object]) -> int:
    seq = event["seq"]
    return seq if isinstance(seq, int) else int(str(seq))


_ALIAS = re.compile(r"^[a-z][a-z0-9_-]{1,40}$")


def _clean_alias(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip().lower()
    if not cleaned or not _ALIAS.match(cleaned):
        return None
    return cleaned


def _parent_text(row: dict[str, object]) -> str | None:
    parent = row.get("parent_message_id")
    if parent is None:
        return None
    return str(parent)


def _capabilities(value: list[str]) -> list[str]:
    """What a tenant says a model can do, from the known set and without repeats."""
    from ar_domain.models.aliases import CAPABILITIES  # noqa: PLC0415

    unknown = sorted(set(value) - CAPABILITIES)
    if unknown:
        raise ArError(
            ErrorCode.VALIDATION_FAILED,
            f"Unknown capability: {', '.join(unknown)}. Known: {', '.join(sorted(CAPABILITIES))}.",
        )
    return sorted(set(value))


def _alias_params(value: dict[str, object]) -> dict[str, object]:
    """The parameters an alias sends when the caller gives none: names and plain values."""
    cleaned: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not key or len(key) > 64:
            raise ArError(ErrorCode.VALIDATION_FAILED, "A parameter name is invalid.")
        if not isinstance(item, str | int | float | bool) and item is not None:
            raise ArError(
                ErrorCode.VALIDATION_FAILED,
                f"The parameter {key} must be a number, a text, true, false or empty.",
            )
        cleaned[key] = item
    return cleaned


def _vector_length(kind: str, value: int | None) -> int | None:
    """The vector length an embedding model is asked for. Unset means its own length."""
    if value is None:
        return None
    if kind != "embedding":
        raise ArError(
            ErrorCode.VALIDATION_FAILED, "Only a model of kind embedding has embedding dimensions."
        )
    if isinstance(value, bool) or value <= 0:
        raise ArError(ErrorCode.VALIDATION_FAILED, "Embedding dimensions must be above zero.")
    return int(value)


def _preview(mime_type: str, data: bytes) -> dict[str, object]:
    if mime_type in {"text/csv", "application/csv"}:
        return {"kind": "csv", "rows": csv_rows(data)}
    if mime_type in {
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }:
        return {"kind": "xlsx", "rows": xlsx_rows(data)}
    return {}


_log = get_logger(__name__)


@dataclass
class ChatBehaviour:
    """Product behaviour over dict buckets.

    ``ChatService`` is the in-memory test double. A production request uses
    ``RequestUnit``, loaded from Postgres for that request and discarded on commit.
    """

    # Denied unless the process that builds the store says otherwise (dev and CI do).
    allow_loopback: bool = False
    scanner: str = "none"
    fake_llm_url: str = "http://127.0.0.1:8099/v1"
    deny_cidrs: tuple[str, ...] = DEFAULT_DENY_CIDRS
    providers: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    models: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    aliases: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    agents: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    versions: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    conversations: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    messages: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    runs: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    steps: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    events: dict[uuid.UUID, list[dict[str, object]]] = field(default_factory=dict)
    files: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    # Where file bytes live. None means the configured S3 bucket (``files/objects.py``);
    # a test's setup gives the stand-in from ``ar_testing``.
    objects: ObjectStore | None = None
    blobs: dict[uuid.UUID, bytes] = field(default_factory=dict)
    feedback: dict[tuple[uuid.UUID, uuid.UUID], dict[str, object]] = field(default_factory=dict)
    shares: dict[tuple[uuid.UUID, str, uuid.UUID], dict[str, object]] = field(default_factory=dict)
    usage: dict[tuple[str, str], UsageRecord] = field(default_factory=dict)
    callbacks: list[dict[str, object]] = field(default_factory=list)
    subscribers: dict[uuid.UUID, list[asyncio.Queue[dict[str, object]]]] = field(
        default_factory=dict
    )
    cancel_flags: set[uuid.UUID] = field(default_factory=set)
    sse_counts: dict[str, int] = field(default_factory=dict)
    temporal_up: bool = False
    tasks: list[asyncio.Task[None]] = field(default_factory=list)
    bindings: dict[tuple[object, ...], dict[str, object]] = field(default_factory=dict)
    audit_log: list[dict[str, object]] = field(default_factory=list)
    domain_events: list[dict[str, object]] = field(default_factory=list)
    packs: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    pack_resources: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    catalogue: dict[tuple[str, str, str], dict[str, object]] = field(default_factory=dict)
    favourites: dict[tuple[uuid.UUID, uuid.UUID], set[uuid.UUID]] = field(default_factory=dict)
    builder_sessions: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    fake_models_allowed: bool = True
    demo_tenant_seeded: bool = False
    last_remote_usage: dict[str, int] | None = None
    pack_signature_required: bool = False
    pack_trusted_keys: dict[str, str] = field(default_factory=dict)
    tool_servers: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    tool_server_versions: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    tool_defs: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    tool_versions: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    tool_calls: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    service_connections: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    connector_installs: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    data_connections: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    browser_connections: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    library_documents: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    rule_sets: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    judgements: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    document_checks: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    document_comparisons: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    document_rewrites: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    credential_providers: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    credential_grants: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    oauth_states: dict[str, dict[str, object]] = field(default_factory=dict)
    token_cache: dict[str, bytes] = field(default_factory=dict)
    secret_values: dict[uuid.UUID, bytes] = field(default_factory=dict)
    named_secrets: dict[tuple[str, str], bytes] = field(default_factory=dict)
    tenant_settings: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    tickets: list[dict[str, object]] = field(default_factory=list)
    pets: list[dict[str, object]] = field(default_factory=lambda: [{"id": 1, "name": "doggie"}])
    rate_buckets: dict[str, list[float]] = field(default_factory=dict)
    tools_seeded: bool = False
    tenant_tools_seeded: bool = False
    notifications: list[dict[str, object]] = field(default_factory=list)
    policies: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    policy_versions: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    approvals: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    human_questions: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    agent_api_keys: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    agent_api_idempotency: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    agent_api_grants: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    a2a_tasks: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    agent_rate_hits: dict[str, list[float]] = field(default_factory=dict)
    approval_decisions: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    standing_approvals: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    review_queues: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    review_items: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    signoffs: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    sod_constraints: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    user_roles: dict[uuid.UUID, set[str]] = field(default_factory=dict)
    user_groups: dict[uuid.UUID, list[str]] = field(default_factory=dict)
    display_names: dict[uuid.UUID, str] = field(default_factory=dict)
    routines: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    routine_events: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    routine_daily: dict[str, int] = field(default_factory=dict)
    user_statuses: dict[uuid.UUID, str] = field(default_factory=dict)
    reauth_users: set[uuid.UUID] = field(default_factory=set)
    delegation_tokens: set[uuid.UUID] = field(default_factory=set)
    temporal_schedules: dict[str, dict[str, object]] = field(default_factory=dict)
    delivery_posts: list[dict[str, object]] = field(default_factory=list)
    channel_integrations: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    channel_identities: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    channel_threads: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    channel_posts: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    approval_lock: threading.Lock = field(default_factory=threading.Lock)
    opa_url: str = ""
    opa_timeout_ms: int = 200
    opa_bundle: bytes = b""
    opa_etag: str = ""
    input_responses: dict[uuid.UUID, str] = field(default_factory=dict)
    sandbox_templates: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    sandboxes: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    sandbox_locks: dict[str, threading.Lock] = field(default_factory=dict)
    knowledge_collections: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    knowledge_sources: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    knowledge_documents: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    document_chunks: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    ingestion_jobs: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    knowledge_blobs: dict[uuid.UUID, bytes] = field(default_factory=dict)
    user_emails: dict[uuid.UUID, str] = field(default_factory=dict)
    user_clearance: dict[uuid.UUID, str] = field(default_factory=dict)
    group_keys: dict[str, str] = field(default_factory=dict)
    memory_facts: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    user_settings: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    team_roster: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    memory_extracted: set[object] = field(default_factory=set)
    memory_seeded: bool = False
    skills: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    skill_versions: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    model_gateway_url: str = ""
    sandbox_launcher: object | None = None
    temporal_client: object | None = None
    # When set, a missing worker is a refusal. The turn is not run in this process.
    temporal_required: bool = False
    # Production posts every tool call to mcp-gateway. Dev and unit tests stay in process.
    tool_gateway_http: bool = False
    # Set only on the sandbox manager. No other process may create pods.
    pod_creator: object | None = None
    event_bus: object | None = None
    watch_polls: int = 240
    durable: bool = False
    durable_engine: AsyncEngine | None = None
    tenant_binding: object | None = None
    reloading: bool = False
    quotas: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    quota_counters: dict[str, tuple[int, datetime]] = field(default_factory=dict)
    quota_lock: threading.Lock = field(default_factory=threading.Lock)
    usage_daily: dict[tuple[str, ...], object] = field(default_factory=dict)
    eval_suites: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    eval_cases: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    eval_runs: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    eval_results: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    feedback_digest: dict[str, dict[str, object]] = field(default_factory=dict)
    eval_gateway: dict[str, int] = field(default_factory=dict)
    eval_platform_tenants: set[uuid.UUID] = field(default_factory=set)
    records: dict[str, dict[object, dict[str, object]]] = field(default_factory=dict)
    workspace_files: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    job_progress: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    a2a_push_configs: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    tool_search_vectors: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    cache_limits: dict[str, int] = field(default_factory=dict)
    evicted_conversations: set[uuid.UUID] = field(default_factory=set)
    _ingest_worker: bool = False

    def __post_init__(self) -> None:
        if self.fake_llm_url == "http://127.0.0.1:8099/v1":
            self.fake_llm_url = fake_llm_base_url()
        # A store starts with the built-in tool catalogue, which belongs to no tenant, and
        # nothing else: no tenant, no model provider, no model and no alias. Those are rows
        # in its database, put there by the people who run it. A test builds the demo
        # tenant and its scripted provider with ``ar_testing.demo``.
        from ar_domain.tools.registry import ToolRegistry  # noqa: PLC0415

        ToolRegistry(self).ensure_seed(tenant=False)

    def ensure_assistant(self, tenant_id: uuid.UUID, user_id: uuid.UUID) -> dict[str, object]:
        """Create the published ``assistant`` agent for a tenant once."""
        for agent in self.agents.values():
            if agent["tenant_id"] == tenant_id and agent["slug"] == "assistant":
                return agent
        agent_id = new_id()
        version_id = new_id()
        now = utcnow()
        definition = assistant_definition(fixtures=self.fake_models_allowed)
        version = {
            "id": version_id,
            "tenant_id": tenant_id,
            "agent_id": agent_id,
            "version": 1,
            "state": "published",
            "definition": definition,
            "change_note": "seed",
            "created_by": user_id,
            "created_at": now,
            "published_at": now,
            "published_by": user_id,
        }
        self.versions[version_id] = version
        agent = {
            "id": agent_id,
            "tenant_id": tenant_id,
            "slug": "assistant",
            "name": "Assistant",
            "description": "Default assistant",
            "owner_user_id": user_id,
            "owner_team_id": None,
            "visibility": "tenant",
            "status": "published",
            "disabled": False,
            "risk_tier": "low",
            "draft_version_id": None,
            "published_version_id": version_id,
            "created_at": now,
            "updated_at": now,
        }
        self.agents[agent_id] = agent
        return agent

    def _provider(
        self,
        provider_id: uuid.UUID,
        tenant_id: uuid.UUID | None,
        name: str,
        kind: str,
        base_url: str,
    ) -> dict[str, object]:
        now = utcnow()
        return {
            "id": provider_id,
            "tenant_id": tenant_id,
            "name": name,
            "kind": kind,
            "base_url": base_url,
            "status": "active",
            "timeout_s": 120,
            "health": {},
            "created_at": now,
            "updated_at": now,
            "platform": tenant_id is None,
        }

    def _model(
        self,
        model_id: uuid.UUID,
        tenant_id: uuid.UUID | None,
        provider_id: uuid.UUID,
        name: str,
        kind: str,
    ) -> dict[str, object]:
        now = utcnow()
        return {
            "id": model_id,
            "tenant_id": tenant_id,
            "provider_id": provider_id,
            "name": name,
            "upstream_model": name,
            "kind": kind,
            "capabilities": ["streaming"],
            "price_input_micros_per_mtok": 0,
            "price_output_micros_per_mtok": 0,
            "request_options": {},
            "status": "active",
            "platform": tenant_id is None,
            "created_at": now,
            "updated_at": now,
        }

    def _alias(
        self,
        alias_id: uuid.UUID,
        tenant_id: uuid.UUID | None,
        alias: str,
        kind: str,
        model_id: uuid.UUID,
    ) -> dict[str, object]:
        now = utcnow()
        return {
            "id": alias_id,
            "tenant_id": tenant_id,
            "alias": alias,
            "kind": kind,
            "primary_model_id": model_id,
            "fallback_model_ids": [],
            "default_params": default_alias_params(kind),
            "status": "active",
            "platform": tenant_id is None,
            "created_at": now,
            "updated_at": now,
        }

    def _owned(
        self, rows: dict[uuid.UUID, dict[str, object]], tenant_id: uuid.UUID
    ) -> list[dict[str, object]]:
        visible: list[dict[str, object]] = []
        for row in rows.values():
            owner = row.get("tenant_id")
            if owner is None or owner == tenant_id:
                visible.append(self._public(row))
        return visible

    def _public(self, row: dict[str, object]) -> dict[str, object]:
        out: dict[str, object] = {}
        for key, value in row.items():
            if key in {"blob", "api_key", "legacy"}:
                continue
            if isinstance(value, datetime):
                out[key] = value.isoformat()
            elif isinstance(value, uuid.UUID):
                out[key] = str(value)
            else:
                out[key] = value
        if "base_url" in row:
            out["has_api_key"] = bool(row.get("api_key") or row.get("has_api_key"))
        if row.get("role") == "assistant" and row.get("status") == "failed":
            out["error"] = reply_error(self, row)
        return out

    def _require(
        self, rows: dict[uuid.UUID, dict[str, object]], item_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> dict[str, object]:
        row = rows.get(item_id)
        if row is None:
            raise NotFoundError()
        owner = row.get("tenant_id")
        if owner is not None and owner != tenant_id:
            raise NotFoundError()
        return row

    def list_providers(self, tenant_id: uuid.UUID) -> list[dict[str, object]]:
        return self._owned(self.providers, tenant_id)

    def create_provider(
        self,
        tenant_id: uuid.UUID | None,
        name: str,
        kind: str,
        base_url: str,
        *,
        platform: bool,
        api_key: str | None = None,
    ) -> dict[str, object]:
        if provider_url_denied(base_url, self.deny_cidrs, allow_loopback=self.allow_loopback):
            raise ArError(ErrorCode.BAD_REQUEST, "provider URL is not allowed")
        if kind not in {"openai_compatible", "vllm", "tei", "fake"}:
            raise ArError(ErrorCode.VALIDATION_FAILED, "unknown provider kind")
        provider_id = new_id()
        owner = None if platform else tenant_id
        row = self._provider(provider_id, owner, name, kind, base_url)
        if api_key:
            row["api_key"] = api_key
            row["has_api_key"] = True
        else:
            row["has_api_key"] = False
        self.providers[provider_id] = row
        return self._public(row)

    def update_provider(
        self,
        tenant_id: uuid.UUID,
        provider_id: uuid.UUID,
        *,
        platform: bool,
        name: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
    ) -> dict[str, object]:
        """Rename a provider, point it at another address, or replace its key."""
        row = self._writable(self.providers, provider_id, tenant_id, platform=platform)
        if base_url:
            if provider_url_denied(base_url, self.deny_cidrs, allow_loopback=self.allow_loopback):
                raise ArError(ErrorCode.BAD_REQUEST, "provider URL is not allowed")
            row["base_url"] = base_url
        if name:
            row["name"] = name
        if api_key:
            row["api_key"] = api_key
            row["has_api_key"] = True
        row["updated_at"] = utcnow()
        return self._public(row)

    def delete_provider(
        self, tenant_id: uuid.UUID, provider_id: uuid.UUID, *, platform: bool
    ) -> None:
        """Remove a provider that no model uses any more."""
        self._writable(self.providers, provider_id, tenant_id, platform=platform)
        used = sorted(
            str(row.get("name"))
            for row in self.models.values()
            if row.get("provider_id") == provider_id
        )
        if used:
            names = ", ".join(used)
            raise ConflictError(f"This provider still has models: {names}. Remove them first.")
        del self.providers[provider_id]

    async def test_provider(
        self, tenant_id: uuid.UUID, provider_id: uuid.UUID
    ) -> dict[str, object]:
        row = self._require(self.providers, provider_id, tenant_id)
        key = await self._provider_key(row)
        models = [item for item in self.models.values() if item.get("provider_id") == provider_id]
        chat = next((item for item in models if item.get("kind") == "chat"), None)
        if chat is None and models:
            # A provider that only serves embeddings or reranking is tested with one of those.
            return await self._probe_vectors(tenant_id, models[0])
        if chat is None:
            return await self._probe_listing(str(row["base_url"]), key)
        return await self._probe_live(str(row["base_url"]), str(chat.get("upstream_model")), key)

    async def _probe_listing(self, base_url: str, api_key: str) -> dict[str, object]:
        """Test a provider that has no model yet: ask it which models it serves.

        No model name is made up to call it with. A provider that answers and accepts the
        key passes; registering a model and testing that is the next step.
        """
        started = time.perf_counter()
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        ok = False
        output = "provider test failed"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(base_url.rstrip("/") + "/models", headers=headers)
            if response.status_code < 300:
                body = response.json()
                listed = body.get("data") if isinstance(body, dict) else None
                count = len(listed) if isinstance(listed, list) else 0
                ok = True
                output = f"The provider answered and lists {count} models. Add one to use it."
            else:
                output = f"provider test failed ({response.status_code})"
        except httpx.HTTPError, ValueError:
            output = "provider test failed"
        latency = int((time.perf_counter() - started) * 1000)
        return {
            "ok": ok,
            "output": output,
            "model_id": "",
            "latency_ms": latency,
            "ttft_ms": latency,
            "usage": {"tokens_in": 0, "tokens_out": 0},
        }

    async def _probe_vectors(
        self, tenant_id: uuid.UUID, model: dict[str, object]
    ) -> dict[str, object]:
        """Ask an embedding or rerank model for one answer and report what it did."""
        from ar_domain.models.embedding import (  # noqa: PLC0415
            embed,
            registered_model,
            rerank,
        )

        provider = self.providers.get(uuid.UUID(str(model["provider_id"])))
        if isinstance(provider, dict) and not provider.get("api_key"):
            key = await self._provider_key(provider)
            if key:
                provider["api_key"] = key
        target = registered_model(self, tenant_id, model.get("id"))
        name = str(model.get("upstream_model") or "")
        started = time.perf_counter()
        ok = False
        if target is None:
            output = "This model or its provider is disabled."
        else:
            try:
                if model.get("kind") == "rerank":
                    scores = await asyncio.to_thread(rerank, target, "test", ["test", "other"])
                    output = f"Returned {len(scores)} scores."
                else:
                    vectors = await asyncio.to_thread(embed, target, ["test"])
                    output = f"Returned a vector of {len(vectors[0])} numbers."
                ok = True
            except ArError as exc:
                output = exc.detail
        latency = int((time.perf_counter() - started) * 1000)
        return {
            "ok": ok,
            "output": output,
            "model_id": name,
            "latency_ms": latency,
            "ttft_ms": latency,
            "usage": {"tokens_in": 1, "tokens_out": 0},
        }

    async def _provider_key(self, provider: dict[str, object]) -> str:
        """The provider's API key, read from the database when this process has not loaded it."""
        key = str(provider.get("api_key") or "")
        provider_id = provider.get("id")
        if not key and self.durable_engine is not None and isinstance(provider_id, uuid.UUID):
            from ar_domain.models.registry import read_api_key  # noqa: PLC0415

            key = await read_api_key(self.durable_engine, provider_id)
        return key

    def list_models(self, tenant_id: uuid.UUID) -> list[dict[str, object]]:
        return self._owned(self.models, tenant_id)

    def create_model(
        self,
        tenant_id: uuid.UUID | None,
        provider_id: uuid.UUID,
        name: str,
        upstream_model: str,
        kind: str,
        *,
        platform: bool,
        price_input_micros_per_mtok: int = 0,
        price_output_micros_per_mtok: int = 0,
        request_options: dict[str, object] | None = None,
        embedding_dimensions: int | None = None,
        capabilities: list[str] | None = None,
    ) -> dict[str, object]:
        self._registry_row(self.providers, provider_id, tenant_id)
        model_id = new_id()
        row = self._model(model_id, None if platform else tenant_id, provider_id, name, kind)
        row["upstream_model"] = upstream_model
        if capabilities is not None:
            row["capabilities"] = _capabilities(capabilities)
        row["embedding_dimensions"] = _vector_length(kind, embedding_dimensions)
        row["price_input_micros_per_mtok"] = max(0, int(price_input_micros_per_mtok))
        row["price_output_micros_per_mtok"] = max(0, int(price_output_micros_per_mtok))
        from ar_domain.models.options import (  # noqa: PLC0415
            copy_request_options,
            default_request_options,
        )

        row["request_options"] = (
            copy_request_options(request_options)
            if request_options is not None
            else default_request_options(upstream_model)
        )
        self.models[model_id] = row
        return self._public(row)

    def request_options(self, tenant_id: uuid.UUID, alias: str) -> dict[str, object]:
        """Provider parameters stored on the model ``alias`` resolves to."""
        from ar_domain.models.options import request_options_of  # noqa: PLC0415

        found = self._alias_target(tenant_id, alias)
        return request_options_of(found[1]) if found is not None else {}

    def model_cost(
        self, tenant_id: uuid.UUID, alias: str, tokens_in: int, tokens_out: int
    ) -> tuple[int, str | None]:
        """Cost in micros for one model call on ``alias`` and the model id it resolved to."""
        from ar_domain.usage.logic import model_cost_micros  # noqa: PLC0415

        found = self._alias_target(tenant_id, alias)
        if found is None:
            return 0, None
        _provider, model = found

        def _price(name: str) -> int:
            value = model.get(name)
            return int(value) if isinstance(value, int) and not isinstance(value, bool) else 0

        cost = model_cost_micros(
            tokens_in,
            tokens_out,
            price_in_per_mtok=_price("price_input_micros_per_mtok"),
            price_out_per_mtok=_price("price_output_micros_per_mtok"),
        )
        model_id = model.get("id")
        return cost, str(model_id) if model_id is not None else None

    def update_model(
        self,
        tenant_id: uuid.UUID,
        model_id: uuid.UUID,
        *,
        platform: bool,
        name: str | None = None,
        upstream_model: str | None = None,
        price_input_micros_per_mtok: int | None = None,
        price_output_micros_per_mtok: int | None = None,
        request_options: dict[str, object] | None = None,
        embedding_dimensions: int | None = None,
        clear_embedding_dimensions: bool = False,
        capabilities: list[str] | None = None,
    ) -> dict[str, object]:
        """Change what a registered model is called, which upstream model it is, its prices,
        or the vector length an embedding model is asked for."""
        row = self._writable(self.models, model_id, tenant_id, platform=platform)
        if capabilities is not None:
            row["capabilities"] = _capabilities(capabilities)
        if clear_embedding_dimensions:
            row["embedding_dimensions"] = None
        elif embedding_dimensions is not None:
            row["embedding_dimensions"] = _vector_length(
                str(row.get("kind") or ""), embedding_dimensions
            )
        if name:
            row["name"] = name
        if upstream_model:
            row["upstream_model"] = upstream_model
        if price_input_micros_per_mtok is not None:
            row["price_input_micros_per_mtok"] = max(0, int(price_input_micros_per_mtok))
        if price_output_micros_per_mtok is not None:
            row["price_output_micros_per_mtok"] = max(0, int(price_output_micros_per_mtok))
        if request_options is not None:
            from ar_domain.models.options import copy_request_options  # noqa: PLC0415

            row["request_options"] = copy_request_options(request_options)
        row["updated_at"] = utcnow()
        return self._public(row)

    def delete_model(self, tenant_id: uuid.UUID, model_id: uuid.UUID, *, platform: bool) -> None:
        """Remove a model that no alias points at any more."""
        self._writable(self.models, model_id, tenant_id, platform=platform)
        used: list[str] = []
        for row in self.aliases.values():
            fallbacks = row.get("fallback_model_ids")
            in_fallbacks = isinstance(fallbacks, list) and model_id in fallbacks
            if row.get("primary_model_id") == model_id or in_fallbacks:
                used.append(str(row.get("alias")))
        if used:
            names = ", ".join(sorted(used))
            raise ConflictError(
                f"These aliases still use this model: {names}. Point them elsewhere first."
            )
        indexed = sorted(
            str(row.get("name") or row.get("slug"))
            for row in getattr(self, "knowledge_collections", {}).values()
            if row.get("tenant_id") == tenant_id and row.get("embedding_model_id") == model_id
        )
        if indexed:
            names = ", ".join(indexed)
            raise ConflictError(
                f"These knowledge collections were indexed with this model: {names}. "
                "Re-index them with another embedding model first."
            )
        del self.models[model_id]

    def delete_alias(self, tenant_id: uuid.UUID, alias_id: uuid.UUID, *, platform: bool) -> None:
        """Remove an alias that no published agent names any more."""
        row = self._writable(self.aliases, alias_id, tenant_id, platform=platform)
        name = str(row.get("alias") or "")
        covered = any(
            other.get("tenant_id") is None and other.get("alias") == name
            for other in self.aliases.values()
        )
        users = [] if covered else self._agents_naming_alias(tenant_id, name)
        if users:
            agents = ", ".join(users)
            raise ConflictError(
                f"These published agents use this alias: {agents}. "
                "Point the alias at another model, or change the agents first."
            )
        del self.aliases[alias_id]

    def _agents_naming_alias(self, tenant_id: uuid.UUID, name: str) -> list[str]:
        """Names of the tenant's published agents whose definition names this alias."""
        found: list[str] = []
        for agent in self.agents.values():
            if agent.get("tenant_id") != tenant_id:
                continue
            published = agent.get("published_version_id")
            version = self.versions.get(published) if isinstance(published, uuid.UUID) else None
            definition = version.get("definition") if isinstance(version, dict) else None
            model = definition.get("model") if isinstance(definition, dict) else None
            if isinstance(model, dict) and name in {
                model.get("alias"),
                model.get("fast_alias"),
                model.get("vision_alias"),
            }:
                found.append(str(agent.get("name") or agent.get("slug")))
        return sorted(found)

    def _same_kind(self, alias_kind: str, model_id: uuid.UUID) -> None:
        """An alias points only at models of its own kind."""
        model = self.models.get(model_id)
        kind = str(model.get("kind") or "") if isinstance(model, dict) else ""
        if kind and kind != alias_kind:
            label = str(model.get("name")) if isinstance(model, dict) else str(model_id)
            raise ArError(
                ErrorCode.VALIDATION_FAILED,
                f"This alias is of kind {alias_kind}, and {label} is of kind {kind}. "
                f"Choose a model of kind {alias_kind}.",
            )

    def list_aliases(self, tenant_id: uuid.UUID) -> list[dict[str, object]]:
        return self._owned(self.aliases, tenant_id)

    def create_alias(
        self,
        tenant_id: uuid.UUID | None,
        alias: str,
        kind: str,
        model_id: uuid.UUID,
        *,
        platform: bool,
        fallback_model_ids: list[uuid.UUID] | None = None,
        default_params: dict[str, object] | None = None,
    ) -> dict[str, object]:
        if not valid_alias(alias):
            raise ArError(ErrorCode.VALIDATION_FAILED, "alias is invalid")
        for existing in self.aliases.values():
            if existing.get("tenant_id") == tenant_id and existing.get("alias") == alias:
                raise ConflictError("a model alias with that name already exists")
        self._registry_row(self.models, model_id, tenant_id)
        for target in (model_id, *(fallback_model_ids or [])):
            self._registry_row(self.models, target, tenant_id)
            self._same_kind(kind, target)
        alias_id = new_id()
        row = self._alias(alias_id, None if platform else tenant_id, alias, kind, model_id)
        row["fallback_model_ids"] = list(fallback_model_ids or [])
        if default_params is not None:
            row["default_params"] = _alias_params(default_params)
        self.aliases[alias_id] = row
        self._embeddings_changed(row)
        return self._public(row)

    def update_alias(
        self,
        tenant_id: uuid.UUID,
        alias_id: uuid.UUID,
        model_id: uuid.UUID,
        *,
        platform: bool,
        actor_user_id: uuid.UUID | None = None,
        fallback_model_ids: list[uuid.UUID] | None = None,
        default_params: dict[str, object] | None = None,
    ) -> dict[str, object]:
        """Point an alias at a new model and re-run gated suites for agents that use it."""
        row = self._writable(self.aliases, alias_id, tenant_id, platform=platform)
        for target in (model_id, *(fallback_model_ids or [])):
            self._require(self.models, target, tenant_id)
            self._same_kind(str(row.get("kind") or "chat"), target)
        row["primary_model_id"] = model_id
        if fallback_model_ids is not None:
            row["fallback_model_ids"] = list(fallback_model_ids)
        if default_params is not None:
            row["default_params"] = _alias_params(default_params)
        row["updated_at"] = utcnow()
        owner = tenant_id if row.get("tenant_id") is None else row.get("tenant_id")
        if isinstance(owner, uuid.UUID) and actor_user_id is not None:
            from ar_domain.agents.access import Actor  # noqa: PLC0415
            from ar_domain.evals.reports import rerun_gated_suites  # noqa: PLC0415
            from ar_domain.identity.permissions import PERMISSION_KEYS  # noqa: PLC0415

            # The suites run as the person who changed the alias.
            rerun_gated_suites(
                self,
                Actor(tenant_id=owner, user_id=actor_user_id, permissions=PERMISSION_KEYS),
                str(row.get("alias") or ""),
            )
        self._embeddings_changed(row)
        return self._public(row)

    def _embeddings_changed(self, alias_row: dict[str, object]) -> None:
        """After the ``embed`` alias moves, memory embeds its facts again with the new model.

        Until then older facts are matched by their words (OQ-102). The work runs beside
        the request that made the change, on this process's loop, and is saved as it goes;
        a script or a test with no loop does it here and now.
        """
        from ar_domain.models.embedding import EMBED_ALIAS  # noqa: PLC0415

        if str(alias_row.get("alias") or "") != EMBED_ALIAS:
            return
        tenant_id = alias_row.get("tenant_id")
        if not isinstance(tenant_id, uuid.UUID):
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            try:
                self._reembed_memory(tenant_id)
            except Exception as exc:  # noqa: BLE001 - the alias change stands; facts match by words
                _log.warning("memory_reembed_failed", error_type=type(exc).__name__)
            return
        self.tasks.append(loop.create_task(self._reembed_memory_soon(tenant_id)))

    async def _reembed_memory_soon(self, tenant_id: uuid.UUID) -> None:
        from ar_common.offload import run_sync  # noqa: PLC0415

        try:
            await run_sync(self._reembed_memory, tenant_id)
        except Exception as exc:  # noqa: BLE001 - the next change or the script tries again
            _log.warning("memory_reembed_failed", error_type=type(exc).__name__)

    def _reembed_memory(self, tenant_id: uuid.UUID) -> int:
        from ar_domain.memory.vectors import reembed  # noqa: PLC0415

        count = reembed(self, tenant_id)
        if count:
            _log.info("memory_reembedded", count=count)
            self.flush_soon()
        return count

    def _registry_row(
        self,
        rows: dict[uuid.UUID, dict[str, object]],
        item_id: uuid.UUID,
        tenant_id: uuid.UUID | None,
    ) -> dict[str, object]:
        """A row the caller may build on: its own, or one that belongs to no tenant."""
        row = rows.get(item_id)
        if row is None:
            raise NotFoundError()
        owner = row.get("tenant_id")
        if owner is not None and owner != tenant_id:
            raise NotFoundError()
        return row

    def resolve(self, tenant_id: uuid.UUID, name: str) -> AliasRef | None:
        refs = [
            AliasRef(
                tenant_id=None if row["tenant_id"] is None else str(row["tenant_id"]),
                alias=str(row["alias"]),
                kind=str(row["kind"]),
                primary_model_id=str(row["primary_model_id"]),
                fallback_model_ids=_string_tuple(row["fallback_model_ids"]),
                status=str(row["status"]),
                default_params=_object_dict(row["default_params"]),
            )
            for row in self.aliases.values()
        ]
        return resolve_alias(refs, str(tenant_id), name)

    async def test_model(self, tenant_id: uuid.UUID, model_id: uuid.UUID) -> dict[str, object]:
        """Ask one registered model for an answer and report what it did."""
        model = self._require(self.models, model_id, tenant_id)
        if model.get("kind") in {"embedding", "rerank"}:
            return await self._probe_vectors(tenant_id, model)
        provider = self.providers[uuid.UUID(str(model["provider_id"]))]
        return await self._probe_live(
            str(provider["base_url"]),
            str(model["upstream_model"]),
            await self._provider_key(provider),
        )

    async def test_alias(
        self, tenant_id: uuid.UUID, alias_id: uuid.UUID, messages: list[dict[str, str]]
    ) -> dict[str, object]:
        row = self._require(self.aliases, alias_id, tenant_id)
        model = self.models.get(uuid.UUID(str(row["primary_model_id"])))
        if model is None:
            raise NotFoundError("model not found")
        if model.get("kind") in {"embedding", "rerank"}:
            return await self._probe_vectors(tenant_id, model)
        provider = self.providers[uuid.UUID(str(model["provider_id"]))]
        return await self._probe_live(
            str(provider["base_url"]),
            str(model["upstream_model"]),
            await self._provider_key(provider),
            messages,
        )

    def _writable(
        self,
        rows: dict[uuid.UUID, dict[str, object]],
        item_id: uuid.UUID,
        tenant_id: uuid.UUID,
        *,
        platform: bool,
    ) -> dict[str, object]:
        row = rows.get(item_id)
        if row is None:
            raise NotFoundError()
        owner = row.get("tenant_id")
        if owner is None and not platform:
            raise ArError(ErrorCode.FORBIDDEN, "platform rows are read-only")
        if owner is not None and owner != tenant_id:
            raise NotFoundError()
        return row

    async def _probe_live(
        self,
        base_url: str,
        model: str,
        api_key: str,
        messages: list[dict[str, str]] | None = None,
    ) -> dict[str, object]:
        """Ask a provider for one answer and report what it did. The key stays in the header.

        With no ``messages`` the provider is asked for the word pong and passes when it
        says so. With ``messages`` it passes when it returns any text. An endpoint that
        does not answer is a failure; no answer is made up for it.
        """
        from ar_domain.models.options import (  # noqa: PLC0415
            apply_request_options,
            default_request_options,
            request_options_of,
        )

        started = time.perf_counter()
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        body: dict[str, object] = {
            "model": model,
            "messages": messages
            or [{"role": "user", "content": "Reply with the single word pong."}],
            "max_tokens": 64 if messages else 32,
        }
        options = next(
            (
                request_options_of(row)
                for row in self.models.values()
                if str(row.get("upstream_model")) == model and row.get("request_options")
            ),
            default_request_options(model),
        )
        apply_request_options(body, options)
        output = "provider test failed"
        answered = False
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    base_url.rstrip("/") + "/chat/completions", json=body, headers=headers
                )
            if response.status_code < 300:
                text = completion_text(response.json())
                answered = bool(text)
                output = text or "provider test returned no text"
            else:
                output = f"provider test failed ({response.status_code})"
        except httpx.HTTPError:
            output = "provider test failed"
        latency = int((time.perf_counter() - started) * 1000)
        return {
            "ok": answered if messages else "pong" in output.lower(),
            "output": output,
            "model_id": model,
            "latency_ms": latency,
            "ttft_ms": latency,
            "usage": {"tokens_in": 1, "tokens_out": max(1, len(output.split()))},
        }

    def list_agents(self, tenant_id: uuid.UUID, user_id: uuid.UUID) -> list[dict[str, object]]:
        found: list[dict[str, object]] = []
        for agent in self.agents.values():
            view = self._view(agent)
            if can_see_agent(
                view,
                tenant_id=str(tenant_id),
                user_id=str(user_id),
                team_ids=set(),
                manage_all=True,
            ):
                found.append(self._agent_out(agent))
        return found

    def _view(self, agent: dict[str, object]) -> AgentView:
        return AgentView(
            tenant_id=str(agent["tenant_id"]),
            owner_user_id=None if agent["owner_user_id"] is None else str(agent["owner_user_id"]),
            owner_team_id=None if agent["owner_team_id"] is None else str(agent["owner_team_id"]),
            visibility=str(agent["visibility"]),
            status=str(agent["status"]),
            disabled=bool(agent["disabled"]),
        )

    def _agent_out(self, agent: dict[str, object]) -> dict[str, object]:
        published = agent.get("published_version_id")
        version = self.versions.get(published) if isinstance(published, uuid.UUID) else None
        body = self._public(agent)
        body["greeting"] = ""
        body["starter_prompts"] = []
        if version is not None:
            definition = version["definition"]
            if isinstance(definition, dict):
                persona = definition.get("persona", {})
                if isinstance(persona, dict):
                    body["greeting"] = persona.get("greeting", "")
                prompts = definition.get("starter_prompts", [])
                body["starter_prompts"] = prompts
                body["definition"] = definition
        return body

    def get_agent(self, tenant_id: uuid.UUID, agent_id: uuid.UUID) -> dict[str, object]:
        return self._agent_out(self._require(self.agents, agent_id, tenant_id))

    def create_agent(
        self, tenant_id: uuid.UUID, user_id: uuid.UUID, slug: str, name: str
    ) -> dict[str, object]:
        if any(
            row["tenant_id"] == tenant_id and row["slug"] == slug for row in self.agents.values()
        ):
            raise ConflictError("slug already exists")
        agent_id = new_id()
        version_id = new_id()
        now = utcnow()
        definition = assistant_definition(fixtures=self.fake_models_allowed)
        definition["persona"] = {"display_name": name, "greeting": ""}
        self.versions[version_id] = {
            "id": version_id,
            "tenant_id": tenant_id,
            "agent_id": agent_id,
            "version": 1,
            "state": "draft",
            "definition": definition,
            "created_at": now,
        }
        agent = {
            "id": agent_id,
            "tenant_id": tenant_id,
            "slug": slug,
            "name": name,
            "description": "",
            "owner_user_id": user_id,
            "owner_team_id": None,
            "visibility": "private",
            "status": "draft",
            "disabled": False,
            "risk_tier": "low",
            "draft_version_id": version_id,
            "published_version_id": None,
            "created_at": now,
            "updated_at": now,
        }
        self.agents[agent_id] = agent
        return self._agent_out(agent)

    def save_draft(
        self, tenant_id: uuid.UUID, agent_id: uuid.UUID, definition: dict[str, object]
    ) -> dict[str, object]:
        agent = self._require(self.agents, agent_id, tenant_id)
        published = agent.get("published_version_id")
        if isinstance(published, uuid.UUID):
            current = self.versions[published]
            if current["state"] == "published" and agent.get("draft_version_id") == published:
                raise ArError(ErrorCode.INVALID_STATE, "published versions are immutable")
        version_id = new_id()
        version_no = 1 + sum(1 for row in self.versions.values() if row["agent_id"] == agent_id)
        self.versions[version_id] = {
            "id": version_id,
            "tenant_id": tenant_id,
            "agent_id": agent_id,
            "version": version_no,
            "state": "draft",
            "definition": definition,
            "created_at": utcnow(),
        }
        agent["draft_version_id"] = version_id
        return self._public(self.versions[version_id])

    def publish(
        self, tenant_id: uuid.UUID, agent_id: uuid.UUID, user_id: uuid.UUID
    ) -> dict[str, object]:
        actor = Actor(
            tenant_id,
            user_id,
            frozenset({"agents:manage_all", "agents:publish", "agents:edit", "agents:create"}),
        )
        return AgentLifecycle(self).publish(actor, agent_id)

    def list_versions(self, tenant_id: uuid.UUID, agent_id: uuid.UUID) -> list[dict[str, object]]:
        self._require(self.agents, agent_id, tenant_id)
        return [self._public(row) for row in self.versions.values() if row["agent_id"] == agent_id]

    def list_conversations(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        *,
        include_previews: bool = False,
    ) -> list[dict[str, object]]:
        rows = [
            self._public(row)
            for row in self.conversations.values()
            if row["tenant_id"] == tenant_id
            and row["user_id"] == user_id
            and row.get("deleted_at") is None
            and (include_previews or not row.get("is_preview"))
        ]
        rows.sort(key=lambda item: str(item.get("updated_at")), reverse=True)
        return rows

    def create_conversation(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        agent_id: uuid.UUID | None,
        *,
        model_alias: str | None = None,
    ) -> dict[str, object]:
        agent = self._pick_agent(tenant_id, user_id, agent_id)
        now = utcnow()
        conversation_id = new_id()
        row = {
            "id": conversation_id,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "agent_id": agent["id"],
            "agent_name": agent["name"],
            "title": "New chat",
            "status": "active",
            "pinned": False,
            "is_preview": False,
            "agent_version_id": agent.get("published_version_id"),
            "model_alias": self._chat_alias(tenant_id, model_alias),
            "active_run_id": None,
            "plan": [],
            "created_at": now,
            "updated_at": now,
            "deleted_at": None,
        }
        self.conversations[conversation_id] = row
        self._evict()
        return self._public(row)

    def _pick_agent(
        self, tenant_id: uuid.UUID, user_id: uuid.UUID, agent_id: uuid.UUID | None
    ) -> dict[str, object]:
        if agent_id is None:
            for candidate in self.agents.values():
                if candidate["tenant_id"] == tenant_id and candidate["slug"] == "assistant":
                    return candidate
            raise NotFoundError("This tenant has no assistant. Run the tenant seed again.")
        agent: dict[str, object] | None = (
            self.agents.get(agent_id) if agent_id is not None else None
        )
        if agent is None or agent["tenant_id"] != tenant_id:
            raise NotFoundError("agent not found")
        view = self._view(agent)
        if agent.get("disabled"):
            raise ArError(ErrorCode.RESOURCE_DISABLED, "agent is disabled")
        if not can_start_run(
            view,
            can_see=can_see_agent(
                view,
                tenant_id=str(tenant_id),
                user_id=str(user_id),
                team_ids=set(),
                manage_all=False,
            ),
        ):
            raise ArError(ErrorCode.RESOURCE_DISABLED, "agent cannot start runs")
        return agent

    def get_conversation(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID,
        *,
        read_all: bool,
    ) -> dict[str, object]:
        row = self._conversation(tenant_id, user_id, conversation_id, read_all=read_all)
        body = self._public(row)
        body["messages"] = self._visible_messages(conversation_id)
        from ar_domain.jobs.progress import jobs_for  # noqa: PLC0415

        body["jobs"] = jobs_for(self, conversation_id)
        return body

    def _conversation(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID,
        *,
        read_all: bool,
    ) -> dict[str, object]:
        row = self.conversations.get(conversation_id)
        if row is None or row["tenant_id"] != tenant_id or row.get("deleted_at") is not None:
            raise NotFoundError()
        if (
            row["user_id"] != user_id
            and not read_all
            and not self._shared(conversation_id, user_id)
        ):
            raise NotFoundError()
        return row

    def _chat_alias(self, tenant_id: uuid.UUID, value: str | None) -> str | None:
        """The alias a conversation asks for. An embedding or rerank alias cannot answer one."""
        alias = _clean_alias(value)
        if alias is None:
            return None
        kinds = {
            str(row.get("kind") or "chat")
            for row in self.aliases.values()
            if row.get("alias") == alias and row.get("tenant_id") in {None, tenant_id}
        }
        if kinds and "chat" not in kinds:
            raise ArError(
                ErrorCode.VALIDATION_FAILED,
                f"The alias {alias} is for {' and '.join(sorted(kinds))} models. "
                "A conversation needs a chat alias.",
            )
        return alias

    def _shared(self, conversation_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        return any(key[0] == conversation_id and key[2] == user_id for key in self.shares)

    def patch_conversation(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID,
        *,
        title: str | None,
        pinned: bool | None,
        model_alias: str | None = None,
        model_alias_set: bool = False,
    ) -> dict[str, object]:
        row = self._owned_conversation(tenant_id, user_id, conversation_id)
        if title is not None:
            row["title"] = title
        if pinned is not None:
            row["pinned"] = pinned
        if model_alias_set:
            row["model_alias"] = self._chat_alias(tenant_id, model_alias)
        row["updated_at"] = utcnow()
        return self._public(row)

    def delete_conversation(
        self, tenant_id: uuid.UUID, user_id: uuid.UUID, conversation_id: uuid.UUID
    ) -> None:
        row = self._owned_conversation(tenant_id, user_id, conversation_id)
        row["deleted_at"] = utcnow()

    def _owned_conversation(
        self, tenant_id: uuid.UUID, user_id: uuid.UUID, conversation_id: uuid.UUID
    ) -> dict[str, object]:
        row = self._conversation(tenant_id, user_id, conversation_id, read_all=False)
        if row["user_id"] != user_id:
            raise ArError(ErrorCode.FORBIDDEN, "shared viewers are read-only")
        return row

    def _visible_messages(self, conversation_id: uuid.UUID) -> list[dict[str, object]]:
        from ar_domain.chat.eviction import recall_conversation  # noqa: PLC0415

        recall_conversation(self, conversation_id)
        nodes = [
            MessageNode(
                id=str(row["id"]),
                parent_id=_parent_text(row),
                is_active=bool(row.get("is_active_branch")),
            )
            for row in self.messages.values()
            if row["conversation_id"] == conversation_id
        ]
        # Return every message so the branch switcher can see siblings, active first.
        rows = [
            self._public(row)
            for row in self.messages.values()
            if row["conversation_id"] == conversation_id
        ]
        rows.sort(key=lambda item: str(item["created_at"]))
        del nodes
        return rows

    def post_message(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID,
        text: str,
        *,
        attachment_ids: list[uuid.UUID] | None = None,
        parent_message_id: uuid.UUID | None = None,
        schedule: bool = True,
        research: bool = False,
    ) -> dict[str, object]:
        conversation = self._owned_conversation(tenant_id, user_id, conversation_id)
        agent_id = conversation.get("agent_id")
        if isinstance(agent_id, uuid.UUID):
            AgentLifecycle(self).assert_runnable(tenant_id, agent_id)
        active = conversation.get("active_run_id")
        if isinstance(active, uuid.UUID):
            run = self.runs.get(active)
            if run is not None and run_is_active(str(run["status"])):
                raise ArError(ErrorCode.RUN_IN_PROGRESS, "a run is already in progress")
        from ar_domain.usage.service import UsageBook  # noqa: PLC0415

        UsageBook(self).assert_run(tenant_id, user_id, agent_id)
        names = self._attachment_names(tenant_id, user_id, attachment_ids or [])
        now = utcnow()
        message_id = new_id()
        run_id = new_id()
        assistant_id = new_id()
        user_message: dict[str, object] = {
            "id": message_id,
            "tenant_id": tenant_id,
            "conversation_id": conversation_id,
            "run_id": run_id,
            "parent_message_id": parent_message_id,
            "role": "user",
            "content": [{"type": "text", "text": text}],
            "text": text,
            "status": "completed",
            "is_active_branch": True,
            "attachments": names,
            "attachment_ids": list(attachment_ids or []),
            "created_at": now,
            "author_user_id": user_id,
        }
        content: list[dict[str, object]] = [{"type": "text", "text": text}]
        for file_id in attachment_ids or []:
            file = self.files[file_id]
            content.append(
                {
                    "type": "file",
                    "file_id": str(file_id),
                    "name": file["name"],
                    "mime_type": file["mime_type"],
                    "size_bytes": file.get("size_bytes"),
                }
            )
        user_message["content"] = content
        self.messages[message_id] = user_message
        if conversation["title"] == "New chat":
            conversation["title"] = text[:80] or "New chat"
        run = self._new_run(
            tenant_id,
            user_id,
            conversation,
            run_id,
            message_id=message_id,
            trigger="research" if research else "chat",
        )
        if research:
            from ar_domain.research.engine import initial_state  # noqa: PLC0415

            run["mode"] = "research"
            run["checkpoint"] = {"research": initial_state(text)}
            self.audit_log.append(
                {
                    "tenant_id": str(tenant_id),
                    "actor_id": str(user_id),
                    "action": "research.started",
                    "target_type": "run",
                    "target_id": str(run_id),
                    "detail": {"mode": "research"},
                    "outcome": "success",
                    "at": now.isoformat(),
                }
            )
        assistant = {
            "id": assistant_id,
            "tenant_id": tenant_id,
            "conversation_id": conversation_id,
            "run_id": run_id,
            "parent_message_id": message_id,
            "role": "assistant",
            "content": [{"type": "text", "text": ""}],
            "text": "",
            "status": "streaming",
            "is_active_branch": True,
            "created_at": now,
        }
        self.messages[assistant_id] = assistant
        run["assistant_message_id"] = assistant_id
        conversation["active_run_id"] = run_id
        conversation["updated_at"] = now
        if schedule:
            self._schedule(run_id, text, names)
        self._evict()
        return {"message": self._public(user_message), "run": self._public(run)}

    def _new_run(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        conversation: dict[str, object],
        run_id: uuid.UUID,
        *,
        message_id: uuid.UUID,
        trigger: str,
        callback_url: str | None = None,
        on_behalf_of: uuid.UUID | None = None,
    ) -> dict[str, object]:
        from ar_domain.identity.plan_limits import guard  # noqa: PLC0415

        active = sum(
            1
            for item in self.runs.values()
            if item.get("tenant_id") == tenant_id and run_is_active(str(item.get("status")))
        )
        guard(self, tenant_id, "max_concurrent_runs", 1, current=active)
        now = utcnow()
        run = {
            "id": run_id,
            "tenant_id": tenant_id,
            "conversation_id": conversation["id"],
            "agent_id": conversation["agent_id"],
            "user_id": on_behalf_of or user_id,
            "input_message_id": message_id,
            "status": "queued",
            "trigger": trigger,
            "parent_run_id": None,
            "root_run_id": run_id,
            "depth": 0,
            "label": "preview" if conversation.get("is_preview") else None,
            "agent_version_id": self._agent_version_id(conversation),
            "temporal_workflow_id": f"run-{run_id}",
            "temporal_started": self.temporal_client is not None or self.temporal_up,
            "callback_url": callback_url,
            "usage": {"tokens_in": 0, "tokens_out": 0, "model_calls": 0, "cost_micros": 0},
            "error": None,
            "created_at": now,
            "started_at": None,
            "ended_at": None,
        }
        self.runs[run_id] = run
        self.events[run_id] = []
        self._emit(
            run,
            "run.queued",
            {"agent_id": str(conversation["agent_id"]), "input_message_id": str(message_id)},
        )
        return self.runs[run_id]

    def _agent_version_id(self, conversation: dict[str, object]) -> uuid.UUID | None:
        version_id = conversation.get("agent_version_id")
        if isinstance(version_id, uuid.UUID):
            return version_id
        agent_id = conversation.get("agent_id")
        agent = self.agents.get(agent_id) if isinstance(agent_id, uuid.UUID) else None
        if not isinstance(agent, dict):
            return None
        published = agent.get("published_version_id")
        if isinstance(published, uuid.UUID):
            return published
        draft = agent.get("draft_version_id")
        return draft if isinstance(draft, uuid.UUID) else None

    def _completion_url_for(self, tenant_id: uuid.UUID, alias: str, headers: dict[str, str]) -> str:
        """The address of the provider the alias points at, with its key when it has one.

        A provider that needs no key, such as a model server on the tenant's own network,
        is called at its address like any other.
        """
        found = self._alias_target(tenant_id, alias)
        if found is None:
            return self.completion_url()
        provider, _model = found
        base = provider.get("base_url")
        if not isinstance(base, str) or not base or str(provider.get("kind")) == "fake":
            return self.completion_url()
        key = provider.get("api_key")
        if isinstance(key, str) and key:
            headers["Authorization"] = f"Bearer {key}"
        return base.rstrip("/") + "/chat/completions"

    def completion_url(self) -> str:
        """Chat completions. The gateway wins when it is configured."""
        base = (self.model_gateway_url or self.fake_llm_url).rstrip("/")
        if self.model_gateway_url and not base.endswith("/v1"):
            base += "/v1"
        return base + "/chat/completions"

    async def refresh_models(self) -> None:
        """Make the model registry equal the database for the tenant this process serves.

        Another process may have added, changed or deleted a provider, a model or an alias.
        A down database keeps what the store holds.
        """
        engine = self.durable_engine
        tenant_id = getattr(self.tenant_binding, "tenant_id", None)
        if engine is None or not isinstance(tenant_id, uuid.UUID):
            return
        from ar_domain.models.registry import load_registry  # noqa: PLC0415

        try:
            await load_registry(engine, self, tenant_id)
        except Exception:  # noqa: BLE001 — chat still runs on what the store holds
            return

    def _completion_call(
        self, tenant_id: uuid.UUID, alias: str = "reasoning"
    ) -> tuple[str, dict[str, str], float, bool]:
        """Model name, headers, timeout, and whether the provider is real."""
        found = self._alias_target(tenant_id, alias)
        if found is None or str(found[0].get("kind")) == "fake":
            return "fake-chat", {"X-Fake-Script-Set": "echo"}, 3.0, False
        provider, model = found
        raw_timeout = provider.get("timeout_s")
        timeout = 120.0
        if isinstance(raw_timeout, int | float) and not isinstance(raw_timeout, bool):
            timeout = float(raw_timeout)
        return str(model.get("upstream_model") or "reasoning"), {}, max(timeout, 30.0), True

    def _alias_target(
        self, tenant_id: uuid.UUID, alias: str
    ) -> tuple[dict[str, object], dict[str, object]] | None:
        """Prefer a tenant non-fake alias over the platform fake."""
        ranked: list[tuple[int, int, dict[str, object], dict[str, object]]] = []
        for row in self.aliases.values():
            if row.get("alias") != alias or row.get("status") != "active":
                continue
            owner = row.get("tenant_id")
            if owner is not None and owner != tenant_id:
                continue
            model = self.models.get(uuid.UUID(str(row["primary_model_id"])))
            if not isinstance(model, dict):
                continue
            provider = self.providers.get(uuid.UUID(str(model["provider_id"])))
            if not isinstance(provider, dict):
                continue
            fake_rank = 1 if str(provider.get("kind")) == "fake" else 0
            tenant_rank = 0 if owner == tenant_id else 1
            ranked.append((fake_rank, tenant_rank, provider, model))
        if not ranked:
            return None
        ranked.sort(key=lambda item: (item[0], item[1]))
        return ranked[0][2], ranked[0][3]

    async def _ensure_provider_key(self, tenant_id: uuid.UUID, alias: str) -> None:
        """Load a persisted provider key. The value stays off API responses."""
        found = self._alias_target(tenant_id, alias)
        if found is None or self.durable_engine is None:
            return
        provider, _model = found
        if isinstance(provider.get("api_key"), str) and provider.get("api_key"):
            return
        provider_id = provider.get("id")
        if not isinstance(provider_id, uuid.UUID):
            return
        from ar_domain.models.registry import read_api_key  # noqa: PLC0415

        try:
            key = await read_api_key(self.durable_engine, provider_id)
        except Exception:  # noqa: BLE001 — a missing key ring cannot unlock the provider
            return
        if key:
            provider["api_key"] = key
            provider["has_api_key"] = True

    def flush_soon(self) -> None:
        """Persist dirty rows without blocking the caller.

        A request unit commits once, with the repository transaction.
        """
        if getattr(self, "request_scoped", False):
            return
        from ar_domain.durable.flush import schedule_flush  # noqa: PLC0415

        schedule_flush(self)

    def _schedule_resume(self, run_id: uuid.UUID) -> None:
        from ar_domain.orchestration.engine import resume_run  # noqa: PLC0415

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(resume_run(self, run_id))
            return
        self.tasks.append(loop.create_task(resume_run(self, run_id)))

    def _schedule(self, run_id: uuid.UUID, text: str, names: list[str]) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        self.tasks.append(loop.create_task(self._start_turn(run_id, text, names)))

    async def _start_turn(self, run_id: uuid.UUID, text: str, names: list[str]) -> None:
        """Run on the runtime worker when Temporal is connected."""
        client = self.temporal_client
        if client is None:
            await self._run_here_or_stop(run_id, text, names)
            return
        from ar_domain.durable.flush import flush_store  # noqa: PLC0415

        await flush_store(self)
        start = getattr(client, "start_workflow", None)
        if not callable(start):
            await self._run_here_or_stop(run_id, text, names)
            return
        run = self.runs.get(run_id)
        research = isinstance(run, dict) and run.get("mode") == "research"
        workflow_id = f"run-{run_id}"
        if isinstance(run, dict) and isinstance(run.get("temporal_workflow_id"), str):
            workflow_id = str(run["temporal_workflow_id"])
        try:
            await start(
                "ResearchWorkflow" if research else "AgentRunWorkflow",
                {"run_id": str(run_id), "steps": True, "text": text},
                id=workflow_id,
                task_queue="ar-runtime",
            )
        except Exception as exc:  # noqa: BLE001 — required Temporal does not run the turn here
            if type(exc).__name__ == "WorkflowAlreadyStartedError":
                await self._watch(run_id)
                return
            await self._run_here_or_stop(run_id, text, names)
            return
        await self._watch(run_id)

    async def _run_here_or_stop(self, run_id: uuid.UUID, text: str, names: list[str]) -> None:
        """Dev runs the turn here. A required worker that is missing does not."""
        if self.temporal_required:
            self.mark_not_resumed(run_id)
            return
        await self.generate(run_id, text, names)

    def mark_not_resumed(self, run_id: uuid.UUID) -> None:
        """The worker lost this turn. It is failed, not run in this process."""
        run = self.runs.get(run_id)
        if not isinstance(run, dict) or not run_is_active(str(run.get("status"))):
            return
        from ar_domain.runs.failure import fail_run  # noqa: PLC0415

        fail_run(
            self,
            run,
            code="interrupted",
            reason="not_resumed",
            message="The worker lost this turn. It was not resumed.",
        )

    async def _watch(self, run_id: uuid.UUID) -> None:
        """Copy worker events into the SSE queues for this process."""
        from ar_domain.durable.hydrate import reload_run  # noqa: PLC0415

        seen = max((_seq(event) for event in self.events.get(run_id, [])), default=0)
        for poll in range(self.watch_polls):
            await reload_run(self, run_id)
            for event in self.events.get(run_id, []):
                seq = _seq(event)
                if seq <= seen:
                    continue
                seen = seq
                for queue in self.subscribers.get(run_id, []):
                    queue.put_nowait(event)
            run = self.runs.get(run_id)
            status = str(run.get("status") if isinstance(run, dict) else "completed")
            if not run_is_active(status):
                return
            if poll % 20 == 0 and await self._workflow_gone(run_id):
                self.mark_not_resumed(run_id)
                return
            await asyncio.sleep(0.25)

    async def _workflow_gone(self, run_id: uuid.UUID) -> bool:
        """True when Temporal no longer has this turn and the run is still working."""
        client = self.temporal_client
        run = self.runs.get(run_id)
        if client is None or not isinstance(run, dict):
            return False
        if not run_is_working(str(run.get("status"))):
            return False
        handle_for = getattr(client, "get_workflow_handle", None)
        if not callable(handle_for):
            return False
        workflow_id = str(run.get("temporal_workflow_id") or f"run-{run_id}")
        describe = getattr(handle_for(workflow_id), "describe", None)
        if not callable(describe):
            return False
        try:
            described = await describe()
        except Exception as exc:  # noqa: BLE001 - only a missing workflow is a lost turn
            return _workflow_not_found(exc)
        status = getattr(described, "status", None)
        name = str(getattr(status, "name", ""))
        terminal = {"COMPLETED", "FAILED", "CANCELED", "CANCELLED", "TERMINATED", "TIMED_OUT"}
        return name in terminal

    def _prepare_run(
        self,
        run: dict[str, object],
        conversation: dict[str, object],
        agent: dict[str, object],
        text: str,
    ) -> None:
        """Resolve the version, store the prompt hash, and mark the run running."""
        if agent.get("disabled"):
            raise ArError(ErrorCode.RESOURCE_DISABLED, "agent is disabled")
        version_key = conversation.get("agent_version_id") or agent.get("published_version_id")
        if not isinstance(version_key, uuid.UUID):
            version_key = agent.get("draft_version_id")
        version = self.versions[uuid.UUID(str(version_key))]
        definition = version["definition"] if isinstance(version["definition"], dict) else {}
        run["agent_version_id"] = version.get("id")
        self._store_prompt(run, conversation, definition, text)
        run["status"] = "running"
        run["started_at"] = utcnow()

    def _store_prompt(
        self,
        run: dict[str, object],
        conversation: dict[str, object],
        definition: dict[str, object],
        text: str,
    ) -> None:
        """Record ``detail.prompt_hash``. The prompt text stays out of the step."""
        from ar_domain.memory.session import prepare_prompt  # noqa: PLC0415

        digest = prepare_prompt(self, run, conversation, definition, text)
        steps = run.get("steps")
        if not isinstance(steps, list):
            steps = []
            run["steps"] = steps
        steps.append({"kind": "model", "detail": {"prompt_hash": digest}})

    async def _finish_grounded(
        self,
        run: dict[str, object],
        assistant: dict[str, object],
        conversation: dict[str, object],
        grounded: dict[str, object],
    ) -> None:
        answer = str(grounded.get("text") or "")
        raw_citations = grounded.get("citations")
        citations: list[object] = raw_citations if isinstance(raw_citations, list) else []
        assistant_id = assistant["id"]
        for citation in citations:
            if isinstance(citation, dict):
                self._emit(
                    run,
                    "citation.added",
                    {"message_id": str(assistant_id), "citation": citation},
                )
        report = grounded.get("report")
        if isinstance(report, dict):
            self._emit(
                run,
                "message.grounding_checked",
                {"message_id": str(assistant_id), "mode": report.get("mode"), "report": report},
            )
        parts = grounded.get("parts") if isinstance(grounded.get("parts"), list) else []
        assistant["content"] = parts
        assistant["text"] = answer
        assistant["status"] = "completed"
        run["ended_at"] = utcnow()
        run["status"] = "completed"
        run["result_summary"] = answer[:8000]
        conversation["active_run_id"] = None
        provider_usage = self.last_remote_usage
        self.last_remote_usage = None
        usage = (
            {
                "tokens_in": int(provider_usage["tokens_in"]),
                "tokens_out": int(provider_usage["tokens_out"]),
            }
            if provider_usage
            and (provider_usage.get("tokens_in") or provider_usage.get("tokens_out"))
            else {"tokens_in": 1, "tokens_out": max(1, len(answer.split()))}
        )
        run["usage"] = usage
        self._meter(run, usage)
        self._emit(run, "message.completed", {"message_id": str(assistant_id), "text": answer})
        user_text = str(self.messages[uuid.UUID(str(run["input_message_id"]))].get("text") or "")
        self._emit(run, "run.completed", {"final_message_id": str(assistant_id), "usage": usage})
        await self._remember(run, user_text, answer)

    async def generate(self, run_id: uuid.UUID, text: str, names: list[str]) -> None:
        """Run one turn. An unexpected failure ends the run; it is never left working."""
        try:
            await self._generate(run_id, text, names)
        except Exception as exc:  # the run must reach a terminal state
            from ar_domain.tools.agent_loop import fail_unexpected  # noqa: PLC0415

            if not fail_unexpected(self, run_id, exc):
                raise

    async def advance_turn(self, run_id: uuid.UUID, text: str, names: list[str]) -> str:
        """One model call or one tool call. The worker activity is this method."""
        await self._generate(run_id, text, names, one_step=True)
        run = self.runs[run_id]
        if not run_is_active(str(run.get("status"))):
            return "final"
        kind = str(run.get("step_kind") or "")
        if kind in {"tools", "model", "paused"}:
            return kind
        return "model"

    async def _generate(  # noqa: PLR0911, PLR0912, PLR0915
        self, run_id: uuid.UUID, text: str, names: list[str], *, one_step: bool = False
    ) -> None:
        """Stream an answer. ``slow`` in the text delays tokens so Stop is visible."""
        run = self.runs[run_id]
        if str(run.get("mode") or "") == "research":
            from ar_domain.research.driver import advance_research  # noqa: PLC0415

            await advance_research(self, run, text, one_step=one_step)
            return
        if one_step:
            from ar_domain.tools.worker_loop import worker_loop_open  # noqa: PLC0415

            if worker_loop_open(run):
                assistant = self.messages[uuid.UUID(str(run["assistant_message_id"]))]
                prior = self.messages[uuid.UUID(str(run["input_message_id"]))]
                resumed_text = str(prior.get("text") or text)
                from ar_domain.tools.agent_loop import run_agent_loop  # noqa: PLC0415

                if (
                    await run_agent_loop(self, run, assistant, resumed_text, one_step=True)
                    and str(run.get("status")) == "completed"
                ):
                    await self._remember(run, resumed_text, str(assistant.get("text") or ""))
                return
        conversation = self.conversations[uuid.UUID(str(run["conversation_id"]))]
        agent = self.agents[uuid.UUID(str(conversation["agent_id"]))]
        from ar_common.errors import QuotaExceededError  # noqa: PLC0415
        from ar_domain.usage.service import UsageBook  # noqa: PLC0415

        try:
            UsageBook(self).assert_model(
                uuid.UUID(str(run["tenant_id"])), run.get("user_id"), run.get("agent_id")
            )
        except QuotaExceededError as exc:
            assistant_id = uuid.UUID(str(run["assistant_message_id"]))
            self._fail_quota(run, conversation, self.messages[assistant_id], exc)
            return
        await self.refresh_models()
        self._prepare_run(run, conversation, agent, text)
        assistant_id = uuid.UUID(str(run["assistant_message_id"]))
        assistant = self.messages[assistant_id]
        if run.get("context_error") == "context_length_exceeded":
            self._fail_context(run, conversation, assistant)
            return
        self._emit(run, "run.started", {"model_alias": "reasoning"})
        if self.durable_engine is not None:
            from ar_domain.durable.flush import flush_store  # noqa: PLC0415

            await flush_store(self)
        self._emit_recall(run)
        self._emit(
            run,
            "message.started",
            {"message_id": str(assistant_id), "role": "assistant", "model_alias": "reasoning"},
        )
        from ar_domain.skills.turn import maybe_compose  # noqa: PLC0415
        from ar_domain.tools.agent_loop import model_alias_for, read_budget, run_agent_loop  # noqa: PLC0415

        # A scripted composition exists for the offline demo and the unit suite; it never
        # runs where fake models are not allowed. The keyword tool turn is gone (M38a-T04):
        # the model decides every tool call through the agent loop.
        scripted = self.fake_models_allowed
        if scripted and await maybe_compose(self, run, assistant, text):
            return
        from ar_domain.workspace.turn import ground_run  # noqa: PLC0415

        await ground_run(self, run, text)
        if await run_agent_loop(self, run, assistant, text, one_step=one_step):
            if str(run.get("status")) == "completed":
                await self._remember(run, text, str(assistant.get("text") or ""))
            return
        from ar_domain.knowledge.answer import compose  # noqa: PLC0415

        grounded = await compose(self, run, text)
        if grounded is not None:
            await self._finish_grounded(run, assistant, conversation, grounded)
            return
        tokens = await self._tokens(
            text,
            names,
            system=self._system_prompt(run),
            tenant_id=uuid.UUID(str(run["tenant_id"])),
            alias=model_alias_for(self, run),
        )
        built: list[str] = []
        for token in tokens:
            if run_id in self.cancel_flags:
                assistant["status"] = "cancelled"
                assistant["text"] = "".join(built)
                run["status"] = "cancelled"
                run["ended_at"] = utcnow()
                conversation["active_run_id"] = None
                self._emit(run, "run.cancelled", {"by": "user"})
                return
            built.append(token)
            assistant["text"] = "".join(built)
            self._emit(run, "message.delta", {"message_id": str(assistant_id), "text": token})
            await asyncio.sleep(0.01)
        answer = "".join(built)
        version_key = run.get("agent_version_id")
        version = self.versions.get(version_key) if isinstance(version_key, uuid.UUID) else None
        definition = version.get("definition") if isinstance(version, dict) else {}
        limit = budget_exceeded(
            steps=1,
            tokens=len(answer),
            cost_micros=0,
            elapsed_s=0,
            tool_calls=0,
            budget=read_budget(definition if isinstance(definition, dict) else {}),
        )
        from ar_domain.tools.agent_loop import _with_trace  # noqa: PLC0415

        assistant["content"] = _with_trace(answer, run)
        assistant["retrieval"] = run.get("retrieval")
        assistant["loaded_skill"] = run.get("loaded_skill")
        assistant["status"] = "completed"
        run["ended_at"] = utcnow()
        conversation["active_run_id"] = None
        if limit is not None:
            run["status"] = "budget_exceeded"
            self._emit(run, "run.budget_exceeded", {"limit": limit})
            return
        provider_usage = self.last_remote_usage
        self.last_remote_usage = None
        usage = (
            {
                "tokens_in": int(provider_usage["tokens_in"]),
                "tokens_out": int(provider_usage["tokens_out"]),
            }
            if provider_usage
            and (provider_usage.get("tokens_in") or provider_usage.get("tokens_out"))
            else {"tokens_in": max(1, len(text.split())), "tokens_out": max(1, len(answer.split()))}
        )
        run["usage"] = usage
        run["status"] = "completed"
        run["result_summary"] = answer[:8000]
        self._meter(run, usage)
        self._emit(run, "message.completed", {"message_id": str(assistant_id), "text": answer})
        self._emit(run, "run.completed", {"final_message_id": str(assistant_id), "usage": usage})
        await self._remember(run, text, answer)
        callback = run.get("callback_url")
        if isinstance(callback, str) and callback:
            self.callbacks.append(
                {"url": callback, "run_id": str(run_id), "status": "completed", "text": answer}
            )

    async def _tokens(
        self,
        text: str,
        names: list[str],
        *,
        system: str = "",
        tenant_id: uuid.UUID | None = None,
        alias: str = "reasoning",
    ) -> list[str]:
        """The single model call a tool-less agent makes. A missing model is an error.

        There is no scripted or ``fake:`` answer (M38a-T02e): when the alias is not connected
        to a real provider the run fails, the way the agent loop already fails it.
        """
        prefix = f"Attached {', '.join(names)}. " if names else ""
        owner = tenant_id or demo_id("tenant")
        model, headers, timeout_s, real = self._completion_call(owner, alias)
        if not real:
            raise ArError(
                ErrorCode.UPSTREAM_ERROR,
                f"The model alias '{alias}' is not connected to a registered model. "
                "Open Models and point the alias at a provider.",
            )
        await self._ensure_provider_key(owner, alias)
        model, headers, timeout_s, real = self._completion_call(owner, alias)
        # The same endpoint and key the agent loop uses for this alias.
        url = self._completion_url_for(owner, alias, headers)
        remote = await self._remote_completion(
            text,
            system,
            model=model,
            headers=headers,
            timeout_s=timeout_s,
            real=real,
            options=self.request_options(owner, alias),
            url=url,
        )
        return [prefix + (remote or "The model returned an empty answer.")]

    async def _remote_completion(
        self,
        text: str,
        system: str = "",
        *,
        model: str = "fake-chat",
        headers: dict[str, str] | None = None,
        timeout_s: float = 3.0,
        real: bool = False,
        options: dict[str, object] | None = None,
        url: str | None = None,
    ) -> str | None:
        from ar_domain.models.options import apply_request_options  # noqa: PLC0415

        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": text})
        body: dict[str, object] = {"model": model, "messages": messages}
        if real:
            body["max_tokens"] = 700
            apply_request_options(body, options or {})
        try:
            async with httpx.AsyncClient(timeout=timeout_s) as client:
                response = await client.post(
                    url or self.completion_url(),
                    json=body,
                    headers=headers or {},
                )
            if response.status_code >= 300:
                return "The model provider returned an error." if real else None
            payload = response.json()
            text_out = completion_text(payload)
            if real:
                from ar_domain.models.logic import completion_message  # noqa: PLC0415

                parsed_usage = completion_message(payload)["usage"]
                self.last_remote_usage = (
                    {str(key): int(value) for key, value in parsed_usage.items()}
                    if isinstance(parsed_usage, dict)
                    else None
                )
            if text_out:
                return text_out
        except httpx.HTTPError:
            return "The model provider did not answer." if real else None
        else:
            return "The model provider returned an empty answer." if real else None

    async def complete_turn(  # noqa: PLR0911
        self,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
        *,
        tenant_id: uuid.UUID,
        model_alias: str,
    ) -> dict[str, object] | None:
        """One model round, including tool calls. None when a fake provider is silent."""
        from ar_domain.loop.routing import routed_completion, routes_for  # noqa: PLC0415
        from ar_domain.models.logic import completion_message  # noqa: PLC0415

        routes = routes_for(self, tenant_id)
        if routes:
            return await routed_completion(
                self, messages, tools, tenant_id=tenant_id, routes=routes
            )
        model, headers, timeout_s, real = self._completion_call(tenant_id, model_alias)
        if real:
            await self._ensure_provider_key(tenant_id, model_alias)
            model, headers, timeout_s, real = self._completion_call(tenant_id, model_alias)
        body: dict[str, object] = {"model": model, "messages": messages}
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"
        if real:
            from ar_domain.models.options import apply_request_options  # noqa: PLC0415

            body["max_tokens"] = 1500 if tools else 800
            apply_request_options(body, self.request_options(tenant_id, model_alias))
        url = self._completion_url_for(tenant_id, model_alias, headers)
        try:
            async with httpx.AsyncClient(timeout=timeout_s) as client:
                response = await client.post(url, json=body, headers=headers)
        except httpx.HTTPError:
            if not real:
                return None
            return {
                "text": "The model provider did not answer.",
                "tool_calls": [],
                "usage": {"tokens_in": 0, "tokens_out": 0},
                "real": True,
            }
        if response.status_code >= 300:
            if not real:
                return None
            return {
                "text": "The model provider returned an error.",
                "tool_calls": [],
                "usage": {"tokens_in": 0, "tokens_out": 0},
                "real": True,
            }
        try:
            payload = response.json()
        except ValueError:
            if not real:
                return None
            return {
                "text": "",
                "tool_calls": [],
                "usage": {"tokens_in": 0, "tokens_out": 0},
                "real": True,
                "parse_error": "The model provider returned malformed JSON.",
            }
        parsed = completion_message(payload)
        parsed["real"] = real
        return parsed

    def _meter(self, run: dict[str, object], usage: dict[str, int]) -> None:
        """Meter a single-call turn: tokens priced from the resolved model (spec 17 §2)."""
        from ar_domain.tools.agent_loop import model_alias_for  # noqa: PLC0415
        from ar_domain.usage.service import note  # noqa: PLC0415

        request_id = str(run["id"])
        keys = gateway_dedupe_keys(request_id)
        tenant = str(run["tenant_id"])
        now = utcnow()
        user = str(run["user_id"]) if run.get("user_id") else None
        agent = str(run["agent_id"]) if run.get("agent_id") else None
        alias = model_alias_for(self, run)
        tenant_id = uuid.UUID(tenant)
        in_cost, model_id = self.model_cost(tenant_id, alias, usage["tokens_in"], 0)
        out_cost, _ = self.model_cost(tenant_id, alias, 0, usage["tokens_out"])
        usage["cost_micros"] = in_cost + out_cost
        for metric, quantity, cost, key in (
            ("model_input_tokens", usage["tokens_in"], in_cost, keys[0]),
            ("model_output_tokens", usage["tokens_out"], out_cost, keys[1]),
        ):
            note(
                self,
                UsageRecord(
                    tenant,
                    now,
                    metric,
                    quantity,
                    cost,
                    key,
                    user_id=user,
                    agent_id=agent,
                    model_alias=alias,
                    source="model-gateway",
                    run_id=request_id,
                    model_id=model_id,
                    api_key_id=str(run["api_key_id"]) if run.get("api_key_id") else None,
                ),
            )

    def _meter_run(self, run: dict[str, object]) -> None:
        from ar_domain.usage.service import note  # noqa: PLC0415

        note(
            self,
            UsageRecord(
                str(run["tenant_id"]),
                utcnow(),
                "runs",
                1,
                0,
                f"run:{run['id']}",
                user_id=str(run["user_id"]) if run.get("user_id") else None,
                agent_id=str(run["agent_id"]) if run.get("agent_id") else None,
                source="runtime-worker",
            ),
        )

    def _system_prompt(self, run: dict[str, object]) -> str:
        messages = run.get("prompt_messages")
        if (
            isinstance(messages, list)
            and messages
            and isinstance(messages[0], dict)
            and messages[0].get("role") == "system"
        ):
            return str(messages[0].get("content") or "")
        return ""

    def _emit_recall(self, run: dict[str, object]) -> None:
        recalled = run.get("recalled")
        if isinstance(recalled, list) and recalled:
            self._emit(
                run,
                "memory.recalled",
                {
                    "fact_ids": [
                        str(item.get("id")) for item in recalled if isinstance(item, dict)
                    ],
                    "count": len(recalled),
                },
            )
        compaction = run.get("compaction")
        if isinstance(compaction, dict):
            self._emit(
                run,
                "context.compacted",
                {
                    "tokens_before": compaction.get("tokens_before"),
                    "tokens_after": compaction.get("tokens_after"),
                },
            )

    async def _remember(self, run: dict[str, object], user_text: str, answer: str) -> None:
        """After a turn is complete, ask the model what to remember from it.

        The answer is already with the person. Whatever goes wrong here is logged by the
        extraction itself and never changes the turn.
        """
        from ar_domain.memory.extraction import remember_turn  # noqa: PLC0415

        try:
            saved = await remember_turn(self, run, user_text, answer)
        except Exception:  # noqa: BLE001 - extraction never fails the turn
            return
        for fact in saved:
            self._emit(
                run,
                "memory.saved",
                {
                    "fact_id": fact.get("id"),
                    "content": fact.get("content"),
                    "scope": fact.get("scope"),
                    "status": fact.get("status"),
                },
            )

    def _fail_context(
        self,
        run: dict[str, object],
        conversation: dict[str, object],
        assistant: dict[str, object],
    ) -> None:
        del conversation
        fail_run(
            self,
            run,
            code="context_length_exceeded",
            message="This conversation is too long. Start a new one.",
            assistant=assistant,
        )

    def _fail_quota(
        self,
        run: dict[str, object],
        conversation: dict[str, object],
        assistant: dict[str, object],
        exc: object,
    ) -> None:
        del conversation
        fail_run(self, run, code="quota_exceeded", message=str(exc), assistant=assistant)

    def _emit(self, run: dict[str, object], event_type: str, data: dict[str, object]) -> None:
        run_id = uuid.UUID(str(run["id"]))
        seq = len(self.events.setdefault(run_id, [])) + 1
        if event_type == "run.completed":
            self._meter_run(run)
        event = {
            "id": f"{run_id}:{seq}",
            "seq": seq,
            "type": event_type,
            "run_id": str(run_id),
            "conversation_id": str(run["conversation_id"]),
            "data": data,
            "ts": utcnow().isoformat(),
            "tenant_id": str(run.get("tenant_id") or ""),
        }
        if event_type not in {"message.delta", "reasoning.delta"}:
            self.events[run_id].append(event)
        else:
            self.events[run_id].append(event)
        for queue in self.subscribers.get(run_id, []):
            queue.put_nowait(event)
        if not self.reloading:
            self.flush_soon()
            self._publish_event(run_id, event)

    def events_after(
        self, tenant_id: uuid.UUID, run_id: uuid.UUID, after: int
    ) -> list[dict[str, object]]:
        run = self.runs.get(run_id)
        if run is None or run["tenant_id"] != tenant_id:
            raise NotFoundError()
        return [event for event in self.events.get(run_id, []) if _seq(event) > after]

    async def _bus_replay(self, run_id: uuid.UUID, after: int) -> list[dict[str, object]]:
        """Events on the shared stream that this process has not yielded yet."""
        replay = getattr(self.event_bus, "replay", None)
        if not callable(replay):
            return []
        try:
            rows = await replay(run_id, after)
        except Exception:  # noqa: BLE001 - a bus blip falls back to the local buffer
            _log.warning("run_event_bus_replay_failed")
            return []
        if not isinstance(rows, list):
            return []
        return [row for row in rows if isinstance(row, dict)]

    def _publish_event(self, run_id: uuid.UUID, event: dict[str, object]) -> None:
        bus = self.event_bus
        publish = getattr(bus, "publish", None)
        if not callable(publish):
            return
        try:
            publish(run_id, event)
        except Exception:  # noqa: BLE001 - a bus blip must not drop the local event
            _log.warning("run_event_bus_publish_failed")

    async def _pump_bus(self, run_id: uuid.UUID, queue: asyncio.Queue[dict[str, object]]) -> None:
        listen = getattr(self.event_bus, "listen", None)
        if not callable(listen):
            return
        try:
            async for event in listen(run_id):
                if isinstance(event, dict):
                    queue.put_nowait(event)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - the stream ending is not a run failure
            _log.warning("run_event_bus_listen_failed")

    def subscribe(self, run_id: uuid.UUID) -> asyncio.Queue[dict[str, object]]:
        queue: asyncio.Queue[dict[str, object]] = asyncio.Queue()
        self.subscribers.setdefault(run_id, []).append(queue)
        return queue

    def unsubscribe(self, run_id: uuid.UUID, queue: asyncio.Queue[dict[str, object]]) -> None:
        rows = self.subscribers.get(run_id, [])
        if queue in rows:
            rows.remove(queue)

    def acquire_sse(self, user_id: str, limit: int) -> bool:
        current = self.sse_counts.get(user_id, 0)
        if current >= limit:
            return False
        self.sse_counts[user_id] = current + 1
        return True

    def release_sse(self, user_id: str) -> None:
        self.sse_counts[user_id] = max(0, self.sse_counts.get(user_id, 1) - 1)

    async def iter_events(  # noqa: PLR0912
        self,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
        after: int,
        *,
        idle_s: float = 10,
    ) -> AsyncIterator[dict[str, object]]:
        """Yield run events. A silence while the run is working is a heartbeat, not the end.

        A run paused for a person ends the stream: the client reads to the end
        before it shows the approval or question, and opens a new stream afterwards.

        ``idle_s`` is the gap between SSE keep-alive comments (stream-events §3).
        The comment is not stored and does not advance ``seq``.
        """
        for event in self.events_after(tenant_id, run_id, after):
            after = max(after, _seq(event))
            yield event
        for event in await self._bus_replay(run_id, after):
            if _seq(event) <= after:
                continue
            after = _seq(event)
            yield event
        run = self.runs.get(run_id)
        if run is not None and not run_is_working(str(run["status"])) and after > 0:
            return
        queue = self.subscribe(run_id)
        watcher = (
            asyncio.create_task(self._watch(run_id)) if self.durable_engine is not None else None
        )
        pump = None
        if self.event_bus is not None:
            pump = asyncio.create_task(self._pump_bus(run_id, queue))
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=idle_s)
                except TimeoutError:
                    current = self.runs.get(run_id)
                    if current is None or not run_is_working(str(current.get("status"))):
                        return
                    yield {"type": "heartbeat", "seq": after, "data": {}}
                    continue
                if _seq(event) <= after:
                    continue
                after = _seq(event)
                yield event
                if str(event["type"]) in {
                    "run.completed",
                    "run.failed",
                    "run.cancelled",
                    "run.budget_exceeded",
                    "tool_call.approval_required",
                    "input.required",
                }:
                    return
        finally:
            if watcher is not None:
                watcher.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await watcher
            if pump is not None:
                pump.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await pump
            self.unsubscribe(run_id, queue)

    def cancel_run(
        self, tenant_id: uuid.UUID, user_id: uuid.UUID, run_id: uuid.UUID
    ) -> dict[str, object]:
        run = self.runs.get(run_id)
        if run is None or run["tenant_id"] != tenant_id or run["user_id"] != user_id:
            raise NotFoundError()
        if not run_is_active(str(run["status"])):
            raise ArError(ErrorCode.INVALID_STATE, "run is not active")
        status = str(run["status"])
        if status == "waiting_approval":
            pending = run.get("pending_approval")
            approval_id = pending.get("approval_id") if isinstance(pending, dict) else None
            if isinstance(approval_id, uuid.UUID):
                from ar_domain.approvals.service import ApprovalBook  # noqa: PLC0415

                ApprovalBook(self).cancel(Actor(tenant_id, user_id, frozenset()), approval_id)
            return self._public(self.runs[run_id])
        if status == "waiting_input":
            run["status"] = "cancelled"
            run["ended_at"] = utcnow()
            conversation_id = run.get("conversation_id")
            conversation = (
                self.conversations.get(conversation_id)
                if isinstance(conversation_id, uuid.UUID)
                else None
            )
            if isinstance(conversation, dict):
                conversation["active_run_id"] = None
            self._emit(run, "run.cancelled", {"by": "user"})
            return self._public(run)
        self.cancel_flags.add(run_id)
        from ar_domain.skills.delegate import cancel_children  # noqa: PLC0415

        cancel_children(self, run_id)
        return self._public(run)

    def resume_run(
        self, tenant_id: uuid.UUID, user_id: uuid.UUID, run_id: uuid.UUID
    ) -> dict[str, object]:
        """Continue a failed or cancelled run that still has a checkpoint."""
        run = self.runs.get(run_id)
        if run is None or run["tenant_id"] != tenant_id or run["user_id"] != user_id:
            raise NotFoundError()
        if run.get("status") not in {"failed", "cancelled", "interrupted"}:
            raise ArError(ErrorCode.INVALID_STATE, "run cannot be resumed")
        checkpoint = run.get("checkpoint")
        if not isinstance(checkpoint, dict) or not checkpoint:
            raise ArError(ErrorCode.INVALID_STATE, "run has no checkpoint")
        run["status"] = "running"
        run["ended_at"] = None
        self._emit(run, "run.resumed", {"checkpoint": "present"})
        return self._public(run)

    def submit_input(
        self, tenant_id: uuid.UUID, user_id: uuid.UUID, run_id: uuid.UUID, text: str
    ) -> dict[str, object]:
        """Accept a reply while a run is waiting for the person."""
        run = self.runs.get(run_id)
        if run is None or run["tenant_id"] != tenant_id or run["user_id"] != user_id:
            raise NotFoundError()
        if str(run["status"]) != "waiting_input":
            raise ArError(ErrorCode.INVALID_STATE, "run input is not available yet")
        if run.get("pending_question_id"):
            from ar_domain.orchestration.ask import accept_human_answer  # noqa: PLC0415

            accept_human_answer(self, tenant_id, user_id, run, text)
            self._schedule_resume(run_id)
            return self._public(run)
        answer = text.strip() or "Using what you sent."
        self.input_responses[run_id] = answer
        self._emit(run, "input.resolved", {"length": len(answer)})
        assistant_id = run.get("assistant_message_id")
        assistant = self.messages.get(assistant_id) if isinstance(assistant_id, uuid.UUID) else None
        if isinstance(assistant, dict):
            assistant["text"] = answer
            assistant["content"] = [{"type": "text", "text": answer}]
            assistant["status"] = "completed"
        run["status"] = "completed"
        run["ended_at"] = utcnow()
        run["result_summary"] = answer[:8000]
        conversation_id = run.get("conversation_id")
        conversation = (
            self.conversations.get(conversation_id)
            if isinstance(conversation_id, uuid.UUID)
            else None
        )
        if isinstance(conversation, dict):
            conversation["active_run_id"] = None
        if isinstance(assistant, dict):
            self._emit(
                run, "message.completed", {"message_id": str(assistant.get("id")), "text": answer}
            )
        self._emit(run, "run.completed", {"final_message_id": str(assistant_id)})
        return self._public(run)

    def get_run(self, tenant_id: uuid.UUID, run_id: uuid.UUID) -> dict[str, object]:
        run = self.runs.get(run_id)
        if run is None or run["tenant_id"] != tenant_id:
            raise NotFoundError()
        return self._public(run)

    def list_runs(self, tenant_id: uuid.UUID, user_id: uuid.UUID) -> list[dict[str, object]]:
        listed: list[dict[str, object]] = []
        for row in self.runs.values():
            if row["tenant_id"] != tenant_id or row["user_id"] != user_id:
                continue
            body = self._public(row)
            conversation_id = row.get("conversation_id")
            conversation = (
                self.conversations.get(conversation_id)
                if isinstance(conversation_id, uuid.UUID)
                else None
            )
            if isinstance(conversation, dict) and conversation.get("is_preview"):
                body["label"] = "preview"
            listed.append(body)
        return listed

    def list_steps(self, tenant_id: uuid.UUID, run_id: uuid.UUID) -> list[dict[str, object]]:
        self.get_run(tenant_id, run_id)
        return [self._public(row) for row in self.steps.values() if row.get("run_id") == run_id]

    def list_children(self, tenant_id: uuid.UUID, run_id: uuid.UUID) -> list[dict[str, object]]:
        """Child runs started by this run. A missing parent is 404."""
        self.get_run(tenant_id, run_id)
        listed = [
            self._public(row)
            for row in self.runs.values()
            if row.get("tenant_id") == tenant_id and row.get("parent_run_id") == run_id
        ]
        listed.sort(key=lambda item: str(item.get("created_at") or ""))
        return listed

    def create_api_run(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        agent_id: uuid.UUID,
        text: str,
        *,
        callback_url: str | None,
        on_behalf_of: uuid.UUID | None,
        allow_on_behalf: bool,
    ) -> dict[str, object]:
        if on_behalf_of is not None and not allow_on_behalf:
            raise ArError(ErrorCode.FORBIDDEN, "on behalf of is not allowed")
        conversation = self.create_conversation(tenant_id, on_behalf_of or user_id, agent_id)
        conversation_id = uuid.UUID(str(conversation["id"]))
        posted = self.post_message(tenant_id, on_behalf_of or user_id, conversation_id, text)
        run = self.runs[uuid.UUID(str(posted["run"]["id"]))]  # type: ignore[index]
        run["trigger"] = "api"
        run["callback_url"] = callback_url
        return posted

    def regenerate(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID,
        message_id: uuid.UUID,
    ) -> dict[str, object]:
        message = self._message(tenant_id, conversation_id, message_id)
        parent = message.get("parent_message_id")
        source = self.messages.get(parent) if isinstance(parent, uuid.UUID) else message
        if source is None:
            raise NotFoundError()
        text = str(source.get("text") or "")
        if source["role"] == "assistant":
            user_parent = source.get("parent_message_id")
            user_message = (
                self.messages.get(user_parent) if isinstance(user_parent, uuid.UUID) else None
            )
            text = "" if user_message is None else str(user_message.get("text") or "")
            parent_id = user_parent if isinstance(user_parent, uuid.UUID) else None
        else:
            parent_id = source["id"] if isinstance(source["id"], uuid.UUID) else None
        return self.post_message(
            tenant_id, user_id, conversation_id, text, parent_message_id=parent_id
        )

    def edit_message(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID,
        message_id: uuid.UUID,
        text: str,
    ) -> dict[str, object]:
        message = self._message(tenant_id, conversation_id, message_id)
        parent = message.get("parent_message_id")
        parent_id = parent if isinstance(parent, uuid.UUID) else None
        self._deactivate_siblings(conversation_id, parent_id, message_id)
        return self.post_message(
            tenant_id, user_id, conversation_id, text, parent_message_id=parent_id
        )

    def activate_message(
        self, tenant_id: uuid.UUID, conversation_id: uuid.UUID, message_id: uuid.UUID
    ) -> dict[str, object]:
        self._message(tenant_id, conversation_id, message_id)
        nodes = [
            MessageNode(
                id=str(row["id"]),
                parent_id=_parent_text(row),
                is_active=bool(row.get("is_active_branch")),
            )
            for row in self.messages.values()
            if row["conversation_id"] == conversation_id
        ]
        flags = activate_branch(nodes, str(message_id))
        for row in self.messages.values():
            if row["conversation_id"] == conversation_id:
                row["is_active_branch"] = flags.get(str(row["id"]), False)
        return self._public(self.messages[message_id])

    def _deactivate_siblings(
        self, conversation_id: uuid.UUID, parent_id: uuid.UUID | None, keep: uuid.UUID
    ) -> None:
        for row in self.messages.values():
            if (
                row["conversation_id"] == conversation_id
                and row["parent_message_id"] == parent_id
                and row["id"] != keep
            ):
                row["is_active_branch"] = False

    def _message(
        self, tenant_id: uuid.UUID, conversation_id: uuid.UUID, message_id: uuid.UUID
    ) -> dict[str, object]:
        row = self.messages.get(message_id)
        if (
            row is None
            or row["tenant_id"] != tenant_id
            or row["conversation_id"] != conversation_id
        ):
            raise NotFoundError()
        return row

    def set_feedback(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        message_id: uuid.UUID,
        rating: str,
        comment: str,
    ) -> dict[str, object]:
        message = self.messages.get(message_id)
        if message is None or message["tenant_id"] != tenant_id:
            raise NotFoundError()
        if rating not in {"up", "down"}:
            raise ArError(ErrorCode.VALIDATION_FAILED, "rating must be up or down")
        row = {
            "id": new_id(),
            "tenant_id": tenant_id,
            "message_id": message_id,
            "user_id": user_id,
            "rating": rating,
            "comment": comment,
            "created_at": utcnow(),
        }
        self.feedback[(message_id, user_id)] = row
        conversation_id = message.get("conversation_id")
        conversation = (
            self.conversations.get(conversation_id)
            if isinstance(conversation_id, uuid.UUID)
            else None
        )
        agent_id = conversation.get("agent_id") if isinstance(conversation, dict) else None
        agent = self.agents.get(agent_id) if isinstance(agent_id, uuid.UUID) else None
        owner = agent.get("owner_user_id") if isinstance(agent, dict) else user_id
        self.domain_events.append(
            {
                "topic": "feedback.created",
                "payload": {
                    "message_id": str(message_id),
                    "run_id": str(message.get("run_id") or ""),
                    "agent_id": str(agent_id or ""),
                    "rating": rating,
                    "reasons": [],
                    "tenant_id": str(tenant_id),
                    "user_id": str(user_id),
                    "owner_user_id": str(owner or user_id),
                },
                "at": utcnow().isoformat(),
            }
        )
        if rating == "down":
            from ar_domain.evals.reports import note_feedback  # noqa: PLC0415

            payload = self.domain_events[-1]["payload"]
            if isinstance(payload, dict):
                note_feedback(self, payload)
        return self._public(row)

    def delete_feedback(
        self, tenant_id: uuid.UUID, user_id: uuid.UUID, message_id: uuid.UUID
    ) -> None:
        row = self.feedback.get((message_id, user_id))
        if row is None or row["tenant_id"] != tenant_id:
            raise NotFoundError()
        del self.feedback[(message_id, user_id)]

    def add_share(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID,
        principal_type: str,
        principal_id: uuid.UUID,
    ) -> dict[str, object]:
        self._owned_conversation(tenant_id, user_id, conversation_id)
        if principal_type not in {"user", "group", "team"}:
            raise ArError(ErrorCode.VALIDATION_FAILED, "principal type is invalid")
        row = {
            "tenant_id": tenant_id,
            "conversation_id": conversation_id,
            "principal_type": principal_type,
            "principal_id": principal_id,
            "permission": "view",
            "created_by": user_id,
        }
        self.shares[(conversation_id, principal_type, principal_id)] = row
        return self._public(row)

    def list_shares(
        self, tenant_id: uuid.UUID, user_id: uuid.UUID, conversation_id: uuid.UUID
    ) -> list[dict[str, object]]:
        self._conversation(tenant_id, user_id, conversation_id, read_all=False)
        return [
            self._public(row)
            for (conv_id, _kind, _pid), row in self.shares.items()
            if conv_id == conversation_id
        ]

    def delete_share(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID,
        principal_type: str,
        principal_id: uuid.UUID,
    ) -> None:
        self._owned_conversation(tenant_id, user_id, conversation_id)
        self.shares.pop((conversation_id, principal_type, principal_id), None)

    def export_conversation(
        self, tenant_id: uuid.UUID, user_id: uuid.UUID, conversation_id: uuid.UUID, fmt: str
    ) -> dict[str, object]:
        body = self.get_conversation(tenant_id, user_id, conversation_id, read_all=False)
        messages = body["messages"]
        if fmt == "json":
            return {"format": "json", "body": body}
        lines = [f"# {body['title']}"]
        if isinstance(messages, list):
            lines.extend(
                f"\n**{message['role']}**\n\n{message.get('text', '')}"
                for message in messages
                if isinstance(message, dict) and message.get("is_active_branch", True)
            )
        return {"format": "markdown", "body": "\n".join(lines)}

    def _attachment_names(
        self, tenant_id: uuid.UUID, user_id: uuid.UUID, attachment_ids: list[uuid.UUID]
    ) -> list[str]:
        names: list[str] = []
        for file_id in attachment_ids:
            row = self.files.get(file_id)
            if row is None or row["tenant_id"] != tenant_id:
                raise NotFoundError("file not found")
            view = FileView(
                tenant_id=str(row["tenant_id"]),
                owner_user_id=None if row["owner_user_id"] is None else str(row["owner_user_id"]),
                conversation_id=None,
                status=str(row["status"]),
            )
            if not can_read_file(
                view,
                tenant_id=str(tenant_id),
                user_id=str(user_id),
                conversation_owner=False,
                read_all=False,
            ):
                raise NotFoundError("file not found")
            if row["status"] != "ready":
                raise ArError(ErrorCode.INVALID_STATE, "file is not ready")
            names.append(str(row["name"]))
        return names

    def upload_limits(self, tenant_id: uuid.UUID) -> dict[str, object]:
        """The types this tenant's people may attach and the largest file, for the composer."""
        rules = upload_rules(settings_for(self, tenant_id))
        return {"mime_types": list(rules.mime_types), "max_bytes": rules.max_bytes}

    def upload(
        self, tenant_id: uuid.UUID, user_id: uuid.UUID, name: str, mime_type: str, data: bytes
    ) -> dict[str, object]:
        rules = upload_rules(settings_for(self, tenant_id))
        mime_type = typed_by_name(name, mime_type)
        if not rules.allows(mime_type):
            shown = mime_type or "an unknown type"
            raise ArError(
                ErrorCode.UNSUPPORTED_MEDIA_TYPE,
                f"Files of type {shown} cannot be attached here. "
                "An administrator sets the allowed types in the organisation's settings.",
            )
        if len(data) > rules.max_bytes:
            limit = rules.max_bytes // (1024 * 1024)
            raise ArError(
                ErrorCode.PAYLOAD_TOO_LARGE, f"The file is over the {limit} MB limit for an upload."
            )
        from ar_domain.identity.plan_limits import guard  # noqa: PLC0415

        existing = 0
        for row in self.files.values():
            if row.get("tenant_id") != tenant_id or row.get("deleted_at") is not None:
                continue
            size = row.get("size_bytes")
            if isinstance(size, int) and not isinstance(size, bool):
                existing += size
        guard(self, tenant_id, "max_storage_gb", len(data), current=existing)
        file_id = new_id()
        now = utcnow()
        verdict = scan_bytes(data, scanner=self.scanner)
        status = "quarantined" if verdict == "infected" else "ready"
        scan_status = (
            "infected"
            if verdict == "infected"
            else ("skipped" if verdict == "skipped" else "clean")
        )
        preview = _preview(mime_type, data)
        row = {
            "id": file_id,
            "tenant_id": tenant_id,
            "owner_user_id": user_id,
            "kind": "upload",
            "name": name,
            "mime_type": mime_type,
            "size_bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "object_key": object_key(
                str(tenant_id), "upload", f"{now:%Y}", f"{now:%m}", str(file_id)
            ),
            "status": status,
            "scan_status": scan_status,
            "preview": preview,
            "created_at": now,
        }
        from ar_domain.files.objects import keep_bytes  # noqa: PLC0415

        # The bytes go to the object store first: a file the store did not take is not a file.
        keep_bytes(self, row, data)
        self.files[file_id] = row
        self._evict()
        return self._public(row)

    def list_files(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        *,
        conversation_id: uuid.UUID | None = None,
    ) -> list[dict[str, object]]:
        """Files the person uploaded or the computer saved, newest last."""
        found: list[dict[str, object]] = []
        for row in self.files.values():
            if row.get("tenant_id") != tenant_id or row.get("deleted_at") is not None:
                continue
            if row.get("status") == "deleted":
                continue
            if conversation_id is not None and row.get("conversation_id") != conversation_id:
                continue
            owner = row.get("owner_user_id")
            if owner not in {None, user_id} and conversation_id is None:
                continue
            found.append(self._public(row))
        found.sort(key=lambda item: str(item.get("created_at")))
        return found

    def get_file(
        self, tenant_id: uuid.UUID, user_id: uuid.UUID, file_id: uuid.UUID
    ) -> dict[str, object]:
        row = self.files.get(file_id)
        if row is None or row["tenant_id"] != tenant_id or row["owner_user_id"] != user_id:
            raise NotFoundError()
        return self._public(row)

    def file_bytes(
        self, tenant_id: uuid.UUID, user_id: uuid.UUID, file_id: uuid.UUID
    ) -> tuple[bytes, str]:
        self.get_file(tenant_id, user_id, file_id)
        from ar_domain.durability.store import read_blob  # noqa: PLC0415

        data = read_blob(self, file_id)
        if data is None:
            raise NotFoundError()
        return data, str(self.files[file_id]["mime_type"])

    def delete_file(self, tenant_id: uuid.UUID, user_id: uuid.UUID, file_id: uuid.UUID) -> None:
        row = self.files.get(file_id)
        if row is None or row["tenant_id"] != tenant_id or row["owner_user_id"] != user_id:
            raise NotFoundError()
        # Soft delete: the row says so, and the retention sweep removes the object later.
        row["status"] = "deleted"
        row["deleted_at"] = utcnow()
        self.blobs.pop(file_id, None)

    def _evict(self) -> None:
        from ar_domain.chat.eviction import evict_chat_cache  # noqa: PLC0415

        evict_chat_cache(self)


@dataclass
class ChatService(ChatBehaviour):
    """In-memory test double. Staging and production boot must not construct this."""

    def __post_init__(self) -> None:
        from ar_domain.readmodel.boot import refuse_memory_double  # noqa: PLC0415

        refuse_memory_double()
        super().__post_init__()


@dataclass
class RequestUnit(ChatBehaviour):
    """Identity map for one repository transaction. It is not kept on the process."""

    def __post_init__(self) -> None:
        super().__post_init__()
        self.request_scoped = True

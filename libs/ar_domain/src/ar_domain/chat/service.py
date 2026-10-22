"""Memory chat service. Specs 04-07 and 13. SQL tables are the durable schema.

The API process serves this store so a laptop without Postgres can sign in and
chat. ``make seed`` writes the same catalogue into Postgres for the real stack.
"""

import asyncio
import hashlib
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
from ar_common.sandboxkit import csv_rows, xlsx_rows
from ar_common.time import utcnow
from ar_domain.agents.access import Actor
from ar_domain.agents.logic import AgentView, assistant_definition, can_see_agent, can_start_run
from ar_domain.agents.service import AgentLifecycle
from ar_domain.conversations.logic import MessageNode, activate_branch, run_is_active
from ar_domain.files.logic import (
    MAX_UPLOAD_BYTES,
    FileView,
    can_read_file,
    mime_allowed,
    object_key,
    scan_bytes,
)
from ar_domain.models.logic import (
    DEFAULT_DENY_CIDRS,
    AliasRef,
    merge_params,
    provider_url_denied,
    resolve_alias,
    valid_alias,
)
from ar_domain.prompts.assembler import build_prompt
from ar_domain.runs.logic import assemble_context, budget_exceeded, tools_not_supported
from ar_domain.usage.logic import UsageRecord, gateway_dedupe_keys, record_usage

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

DEMO_NS = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


def demo_id(name: str) -> uuid.UUID:
    """Stable id for the in-process demo catalogue."""
    return uuid.uuid5(DEMO_NS, f"ar-dev-{name}")


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


def _seq(event: dict[str, object]) -> int:
    seq = event["seq"]
    return seq if isinstance(seq, int) else int(str(seq))


def _preview(mime_type: str, data: bytes) -> dict[str, object]:
    if mime_type in {"text/csv", "application/csv"}:
        return {"kind": "csv", "rows": csv_rows(data)}
    if mime_type in {
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }:
        return {"kind": "xlsx", "rows": xlsx_rows(data)}
    return {}


@dataclass
class ChatService:
    """Tenant-scoped product behaviour backed by process memory."""

    allow_loopback: bool = True
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
    builder_scripts: list[str] = field(default_factory=list)
    builder_strict: bool = False
    pack_signature_required: bool = False
    pack_trusted_keys: dict[str, str] = field(default_factory=dict)
    tool_servers: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    tool_server_versions: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    tool_defs: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    tool_versions: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    tool_calls: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    data_connections: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    credential_providers: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    credential_grants: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    oauth_states: dict[str, dict[str, object]] = field(default_factory=dict)
    token_cache: dict[str, bytes] = field(default_factory=dict)
    secret_values: dict[uuid.UUID, bytes] = field(default_factory=dict)
    tenant_settings: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    tickets: list[dict[str, object]] = field(default_factory=list)
    pets: list[dict[str, object]] = field(default_factory=lambda: [{"id": 1, "name": "doggie"}])
    rate_buckets: dict[str, list[float]] = field(default_factory=dict)
    tools_seeded: bool = False
    notifications: list[dict[str, object]] = field(default_factory=list)
    policies: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    policy_versions: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
    approvals: dict[uuid.UUID, dict[str, object]] = field(default_factory=dict)
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

    def __post_init__(self) -> None:
        if self.fake_llm_url == "http://127.0.0.1:8099/v1":
            self.fake_llm_url = fake_llm_base_url()
        self.seed_demo()

    def seed_demo(self) -> None:
        """Idempotent demo tenant catalogue: fake-llm, aliases, assistant."""
        if self.providers:
            return
        provider_id = demo_id("provider")
        chat_model = demo_id("model-chat")
        embed_model = demo_id("model-embed")
        rerank_model = demo_id("model-rerank")
        self.providers[provider_id] = self._provider(
            provider_id, None, "fake-llm", "fake", self.fake_llm_url
        )
        self.models[chat_model] = self._model(chat_model, None, provider_id, "fake-chat", "chat")
        self.models[embed_model] = self._model(
            embed_model, None, provider_id, "fake-embed", "embedding"
        )
        self.models[rerank_model] = self._model(
            rerank_model, None, provider_id, "fake-rerank", "rerank"
        )
        for alias, model_id, kind in (
            ("reasoning", chat_model, "chat"),
            ("fast", chat_model, "chat"),
            ("vision", chat_model, "chat"),
            ("embed", embed_model, "embedding"),
            ("rerank", rerank_model, "rerank"),
        ):
            alias_id = demo_id(f"alias-{alias}")
            self.aliases[alias_id] = self._alias(alias_id, None, alias, kind, model_id)
        self.ensure_assistant(demo_id("tenant"), demo_id("admin"))
        AgentLifecycle(self).ensure_builtins(demo_id("tenant"), demo_id("admin"))
        from ar_domain.tools.registry import ToolRegistry  # noqa: PLC0415

        ToolRegistry(self).ensure_seed()

    def seed_showcase(self) -> None:
        """Example threads for the dev admin so the first screen is not empty.

        Stable ids make the insert idempotent. The durable catalogue still comes
        from ``make seed``; this store is the one the dev API serves (OQ-31).
        """
        tenant_id = demo_id("tenant")
        user_id = demo_id("admin")
        marker = demo_id("showcase-status")
        if marker in self.conversations:
            self._seed_chart(tenant_id, user_id)
            self._seed_library(tenant_id, user_id)
            return
        agent = self.ensure_assistant(tenant_id, user_id)
        samples = (
            (
                "showcase-status",
                "Weekly status for the platform",
                "Draft a short status update for the platform team.",
                "\n".join(
                    (
                        "Here is a status you can send.",
                        "",
                        "## This week",
                        "",
                        "- Chat answers stream in place, with a stop control.",
                        "- The workspace directory lists the four seeded roles.",
                        "- Model aliases `reasoning`, `fast` and `vision` point at fake-llm.",
                        "",
                        "Nothing is blocked for the Friday review.",
                    )
                ),
            ),
            (
                "showcase-session",
                "How the session cookie works",
                "Explain the sign-in session in simpler terms, and show a short example.",
                "\n".join(
                    (
                        "The browser keeps a cookie named `ar_session`. The API stores the",
                        "real session on the server, so the cookie is only a lookup key.",
                        "",
                        "```python",
                        "def signed_in(cookie: str, sessions: dict[str, str]) -> bool:",
                        "    return cookie in sessions",
                        "```",
                        "",
                        "A second cookie, `ar_csrf`, travels with any change you make.",
                        "That stops another site from submitting a form as you.",
                    )
                ),
            ),
            (
                "showcase-tone",
                "What the assistant should feel like",
                "Summarise what a calm enterprise assistant should feel like.",
                "\n".join(
                    (
                        "It should feel like a well-run desk.",
                        "",
                        "1. One clear next step, not a wall of settings.",
                        "2. Answers that stay in a readable column.",
                        "3. Light and dark that are both finished.",
                        "",
                        "People open it when they have work to do, and they can see",
                        "where that work stands.",
                    )
                ),
            ),
        )
        now = utcnow()
        for name, title, question, answer in samples:
            conversation_id = demo_id(name)
            question_id = demo_id(f"{name}-q")
            answer_id = demo_id(f"{name}-a")
            created = now
            self.conversations[conversation_id] = {
                "id": conversation_id,
                "tenant_id": tenant_id,
                "user_id": user_id,
                "agent_id": agent["id"],
                "agent_name": agent["name"],
                "title": title,
                "status": "active",
                "pinned": False,
                "active_run_id": None,
                "created_at": created,
                "updated_at": created,
                "deleted_at": None,
                "showcase": True,
            }
            self.messages[question_id] = {
                "id": question_id,
                "tenant_id": tenant_id,
                "conversation_id": conversation_id,
                "run_id": None,
                "parent_message_id": None,
                "role": "user",
                "content": [{"type": "text", "text": question}],
                "text": question,
                "status": "completed",
                "is_active_branch": True,
                "attachments": [],
                "created_at": created,
                "author_user_id": user_id,
            }
            self.messages[answer_id] = {
                "id": answer_id,
                "tenant_id": tenant_id,
                "conversation_id": conversation_id,
                "run_id": None,
                "parent_message_id": question_id,
                "role": "assistant",
                "content": [{"type": "text", "text": answer}],
                "text": answer,
                "status": "completed",
                "is_active_branch": True,
                "created_at": created,
            }
        self._seed_chart(tenant_id, user_id)
        self._seed_library(tenant_id, user_id)

    def _seed_library(self, tenant_id: uuid.UUID, user_id: uuid.UUID) -> None:
        from ar_domain.knowledge.showcase import seed_library  # noqa: PLC0415

        seed_library(self, tenant_id, user_id)

    def _seed_chart(self, tenant_id: uuid.UUID, user_id: uuid.UUID) -> None:
        from ar_domain.sandboxes.service import SandboxBook  # noqa: PLC0415

        SandboxBook(self).seed_chart(tenant_id, user_id)

    def ensure_assistant(self, tenant_id: uuid.UUID, user_id: uuid.UUID) -> dict[str, object]:
        """Create the published ``assistant`` agent for a tenant once."""
        for agent in self.agents.values():
            if agent["tenant_id"] == tenant_id and agent["slug"] == "assistant":
                return agent
        agent_id = new_id()
        version_id = new_id()
        now = utcnow()
        definition = assistant_definition()
        if tools_not_supported(definition):
            raise ArError(ErrorCode.INVALID_STATE, "assistant must not bind tools")
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
            "default_params": {"temperature": 0.2},
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
            if key == "blob":
                continue
            if isinstance(value, datetime):
                out[key] = value.isoformat()
            elif isinstance(value, uuid.UUID):
                out[key] = str(value)
            else:
                out[key] = value
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
    ) -> dict[str, object]:
        if provider_url_denied(base_url, self.deny_cidrs, allow_loopback=self.allow_loopback):
            raise ArError(ErrorCode.BAD_REQUEST, "provider URL is not allowed")
        if kind not in {"openai_compatible", "vllm", "tei", "fake"}:
            raise ArError(ErrorCode.VALIDATION_FAILED, "unknown provider kind")
        provider_id = new_id()
        owner = None if platform else tenant_id
        row = self._provider(provider_id, owner, name, kind, base_url)
        self.providers[provider_id] = row
        return self._public(row)

    def update_provider(
        self, tenant_id: uuid.UUID, provider_id: uuid.UUID, *, platform: bool, name: str | None
    ) -> dict[str, object]:
        row = self._writable(self.providers, provider_id, tenant_id, platform=platform)
        if name:
            row["name"] = name
        row["updated_at"] = utcnow()
        return self._public(row)

    def delete_provider(
        self, tenant_id: uuid.UUID, provider_id: uuid.UUID, *, platform: bool
    ) -> None:
        self._writable(self.providers, provider_id, tenant_id, platform=platform)
        del self.providers[provider_id]

    async def test_provider(
        self, tenant_id: uuid.UUID, provider_id: uuid.UUID
    ) -> dict[str, object]:
        row = self._require(self.providers, provider_id, tenant_id)
        return await self._probe(str(row["base_url"]), "fake-chat")

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
    ) -> dict[str, object]:
        self._require(self.providers, provider_id, tenant_id or demo_id("tenant"))
        model_id = new_id()
        row = self._model(model_id, None if platform else tenant_id, provider_id, name, kind)
        row["upstream_model"] = upstream_model
        self.models[model_id] = row
        return self._public(row)

    def delete_model(self, tenant_id: uuid.UUID, model_id: uuid.UUID, *, platform: bool) -> None:
        self._writable(self.models, model_id, tenant_id, platform=platform)
        del self.models[model_id]

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
    ) -> dict[str, object]:
        if not valid_alias(alias):
            raise ArError(ErrorCode.VALIDATION_FAILED, "alias is invalid")
        self._require(self.models, model_id, tenant_id or demo_id("tenant"))
        alias_id = new_id()
        row = self._alias(alias_id, None if platform else tenant_id, alias, kind, model_id)
        row["fallback_model_ids"] = list(fallback_model_ids or [])
        self.aliases[alias_id] = row
        return self._public(row)

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

    async def test_alias(
        self, tenant_id: uuid.UUID, alias_id: uuid.UUID, messages: list[dict[str, str]]
    ) -> dict[str, object]:
        row = self._require(self.aliases, alias_id, tenant_id)
        model = self.models.get(uuid.UUID(str(row["primary_model_id"])))
        if model is None:
            raise NotFoundError("model not found")
        provider = self.providers[uuid.UUID(str(model["provider_id"]))]
        params = merge_params(_object_dict(row["default_params"]), {"max_tokens": 64})
        del params
        return await self._probe(str(provider["base_url"]), str(model["upstream_model"]), messages)

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

    async def _probe(
        self, base_url: str, model: str, messages: list[dict[str, str]] | None = None
    ) -> dict[str, object]:
        started = time.perf_counter()
        body = messages or [{"role": "user", "content": "ping"}]
        output = f"fake: {body[-1]['content']}"
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.post(
                    base_url.rstrip("/") + "/chat/completions",
                    json={"model": model, "messages": body},
                    headers={"X-Fake-Script-Set": "echo"},
                )
                if response.status_code < 300:
                    payload = response.json()
                    choices = payload.get("choices") or []
                    if choices:
                        output = str(choices[0]["message"]["content"])
        except httpx.HTTPError:
            output = f"fake: {body[-1]['content']}"
        latency = int((time.perf_counter() - started) * 1000)
        return {
            "output": output,
            "model_id": model,
            "latency_ms": latency,
            "ttft_ms": latency,
            "usage": {"tokens_in": 1, "tokens_out": max(1, len(output.split()))},
        }

    def list_agents(self, tenant_id: uuid.UUID, user_id: uuid.UUID) -> list[dict[str, object]]:
        self.ensure_assistant(tenant_id, user_id)
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
        definition = assistant_definition()
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
        self, tenant_id: uuid.UUID, user_id: uuid.UUID, agent_id: uuid.UUID | None
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
            "active_run_id": None,
            "plan": [],
            "created_at": now,
            "updated_at": now,
            "deleted_at": None,
        }
        self.conversations[conversation_id] = row
        return self._public(row)

    def _pick_agent(
        self, tenant_id: uuid.UUID, user_id: uuid.UUID, agent_id: uuid.UUID | None
    ) -> dict[str, object]:
        if agent_id is None:
            self.ensure_assistant(tenant_id, user_id)
            for candidate in self.agents.values():
                if candidate["tenant_id"] == tenant_id and candidate["slug"] == "assistant":
                    return candidate
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
    ) -> dict[str, object]:
        row = self._owned_conversation(tenant_id, user_id, conversation_id)
        if title is not None:
            row["title"] = title
        if pinned is not None:
            row["pinned"] = pinned
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
        nodes = [
            MessageNode(
                id=str(row["id"]),
                parent_id=(
                    None if row["parent_message_id"] is None else str(row["parent_message_id"])
                ),
                is_active=bool(row["is_active_branch"]),
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
        self.messages[message_id] = user_message
        if conversation["title"] == "New chat":
            conversation["title"] = text[:80] or "New chat"
        run = self._new_run(
            tenant_id,
            user_id,
            conversation,
            run_id,
            message_id=message_id,
            trigger="chat",
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
            "label": "preview" if conversation.get("is_preview") else None,
            "temporal_workflow_id": f"run-{run_id}",
            "temporal_started": self.temporal_up,
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
        return run

    def _schedule(self, run_id: uuid.UUID, text: str, names: list[str]) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        self.tasks.append(loop.create_task(self.generate(run_id, text, names)))

    def _prepare_run(
        self,
        run: dict[str, object],
        conversation: dict[str, object],
        agent: dict[str, object],
        text: str,
        names: list[str],
    ) -> None:
        """Resolve the version, store the prompt hash, and mark the run running."""
        if agent.get("disabled"):
            raise ArError(ErrorCode.RESOURCE_DISABLED, "agent is disabled")
        version_key = conversation.get("agent_version_id") or agent.get("published_version_id")
        if not isinstance(version_key, uuid.UUID):
            version_key = agent.get("draft_version_id")
        version = self.versions[uuid.UUID(str(version_key))]
        definition = version["definition"] if isinstance(version["definition"], dict) else {}
        instructions = str(definition.get("instructions", ""))
        assemble_context(
            instructions=instructions,
            history=[{"role": "user", "content": text}],
            attachment_names=names,
        )
        self._store_prompt(run, definition, text, names)
        run["agent_version_id"] = version.get("id")
        run["status"] = "running"
        run["started_at"] = utcnow()

    def _store_prompt(
        self,
        run: dict[str, object],
        definition: dict[str, object],
        text: str,
        names: list[str],
    ) -> None:
        """Record ``detail.prompt_hash``. The prompt text stays out of the step."""
        bundle = build_prompt(
            {
                "definition": definition,
                "user_text": text,
                "files": names,
                "history": [{"role": "user", "content": text}],
            }
        )
        digest = bundle.prompt_hash
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
        citations = grounded.get("citations") if isinstance(grounded.get("citations"), list) else []
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
        usage = {"tokens_in": 1, "tokens_out": max(1, len(answer.split()))}
        run["usage"] = usage
        self._meter(run, usage)
        self._emit(run, "message.completed", {"message_id": str(assistant_id), "text": answer})
        self._emit(run, "run.completed", {"final_message_id": str(assistant_id), "usage": usage})

    async def generate(self, run_id: uuid.UUID, text: str, names: list[str]) -> None:
        """Stream an answer. ``slow`` in the text delays tokens so Stop is visible."""
        run = self.runs[run_id]
        conversation = self.conversations[uuid.UUID(str(run["conversation_id"]))]
        agent = self.agents[uuid.UUID(str(conversation["agent_id"]))]
        self._prepare_run(run, conversation, agent, text, names)
        assistant_id = uuid.UUID(str(run["assistant_message_id"]))
        assistant = self.messages[assistant_id]
        self._emit(run, "run.started", {"model_alias": "reasoning"})
        self._emit(
            run,
            "message.started",
            {"message_id": str(assistant_id), "role": "assistant", "model_alias": "reasoning"},
        )
        from ar_domain.tools.chat_loop import maybe_tools  # noqa: PLC0415

        if await maybe_tools(self, run, assistant, text):
            return
        from ar_domain.knowledge.answer import compose  # noqa: PLC0415

        grounded = compose(self, run, text)
        if grounded is not None:
            await self._finish_grounded(run, assistant, conversation, grounded)
            return
        slow = "slow" in text.lower()
        tokens = await self._tokens(text, names, slow=slow)
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
            await asyncio.sleep(0.8 if slow else 0.01)
        answer = "".join(built)
        limit = budget_exceeded(
            steps=1,
            tokens=len(answer),
            cost_micros=0,
            elapsed_s=0,
            tool_calls=0,
            budget={
                "max_steps": 8,
                "max_tokens": 16000,
                "max_cost_micros": 1_000_000,
                "max_wall_clock_s": 120,
                "max_tool_calls": 0,
            },
        )
        assistant["content"] = [{"type": "text", "text": answer}]
        assistant["status"] = "completed"
        run["ended_at"] = utcnow()
        conversation["active_run_id"] = None
        if limit is not None:
            run["status"] = "budget_exceeded"
            self._emit(run, "run.budget_exceeded", {"limit": limit})
            return
        usage = {"tokens_in": max(1, len(text.split())), "tokens_out": max(1, len(answer.split()))}
        run["usage"] = usage
        run["status"] = "completed"
        run["result_summary"] = answer[:8000]
        self._meter(run, usage)
        self._emit(run, "message.completed", {"message_id": str(assistant_id), "text": answer})
        self._emit(run, "run.completed", {"final_message_id": str(assistant_id), "usage": usage})
        callback = run.get("callback_url")
        if isinstance(callback, str) and callback:
            self.callbacks.append(
                {"url": callback, "run_id": str(run_id), "status": "completed", "text": answer}
            )

    async def _tokens(self, text: str, names: list[str], *, slow: bool) -> list[str]:
        if slow:
            sentence = "This answer is intentionally slow so you can press stop. "
            return [sentence] * 12
        prefix = f"Attached {', '.join(names)}. " if names else ""
        remote = await self._remote_completion(text)
        body = remote if remote else f"fake: {text}"
        return [prefix + body]

    async def _remote_completion(self, text: str) -> str | None:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.post(
                    self.fake_llm_url.rstrip("/") + "/chat/completions",
                    json={
                        "model": "fake-chat",
                        "messages": [{"role": "user", "content": text}],
                    },
                    headers={"X-Fake-Script-Set": "echo"},
                )
            if response.status_code >= 300:
                return None
            payload = response.json()
            choices = payload.get("choices") or []
            if not choices:
                return None
            return str(choices[0]["message"]["content"])
        except httpx.HTTPError:
            return None

    def _meter(self, run: dict[str, object], usage: dict[str, int]) -> None:
        request_id = str(run["id"])
        keys = gateway_dedupe_keys(request_id)
        tenant = str(run["tenant_id"])
        now = utcnow()
        record_usage(
            self.usage,
            UsageRecord(
                tenant,
                now,
                "model_input_tokens",
                usage["tokens_in"],
                0,
                keys[0],
                source="model-gateway",
            ),
        )
        record_usage(
            self.usage,
            UsageRecord(
                tenant,
                now,
                "model_output_tokens",
                usage["tokens_out"],
                0,
                keys[1],
                source="model-gateway",
            ),
        )

    def _emit(self, run: dict[str, object], event_type: str, data: dict[str, object]) -> None:
        run_id = uuid.UUID(str(run["id"]))
        seq = len(self.events[run_id]) + 1
        event = {
            "id": f"{run_id}:{seq}",
            "seq": seq,
            "type": event_type,
            "run_id": str(run_id),
            "conversation_id": str(run["conversation_id"]),
            "data": data,
            "ts": utcnow().isoformat(),
        }
        if event_type not in {"message.delta", "reasoning.delta"}:
            self.events[run_id].append(event)
        else:
            self.events[run_id].append(event)
        for queue in self.subscribers.get(run_id, []):
            queue.put_nowait(event)

    def events_after(
        self, tenant_id: uuid.UUID, run_id: uuid.UUID, after: int
    ) -> list[dict[str, object]]:
        run = self.runs.get(run_id)
        if run is None or run["tenant_id"] != tenant_id:
            raise NotFoundError()
        return [event for event in self.events.get(run_id, []) if _seq(event) > after]

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

    async def iter_events(
        self, tenant_id: uuid.UUID, run_id: uuid.UUID, after: int
    ) -> AsyncIterator[dict[str, object]]:
        for event in self.events_after(tenant_id, run_id, after):
            yield event
        run = self.runs.get(run_id)
        if run is not None and not run_is_active(str(run["status"])) and after > 0:
            return
        queue = self.subscribe(run_id)
        try:
            while True:
                event = await asyncio.wait_for(queue.get(), timeout=15)
                if _seq(event) <= after:
                    continue
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
        except TimeoutError:
            return
        finally:
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
                parent_id=(
                    None if row["parent_message_id"] is None else str(row["parent_message_id"])
                ),
                is_active=bool(row["is_active_branch"]),
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

    def upload(
        self, tenant_id: uuid.UUID, user_id: uuid.UUID, name: str, mime_type: str, data: bytes
    ) -> dict[str, object]:
        if not mime_allowed(mime_type):
            raise ArError(ErrorCode.UNSUPPORTED_MEDIA_TYPE, "file type is not allowed")
        if len(data) > MAX_UPLOAD_BYTES:
            raise ArError(ErrorCode.PAYLOAD_TOO_LARGE, "file is too large")
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
        self.files[file_id] = row
        self.blobs[file_id] = data
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
        return self.blobs[file_id], str(self.files[file_id]["mime_type"])

    def delete_file(self, tenant_id: uuid.UUID, user_id: uuid.UUID, file_id: uuid.UUID) -> None:
        row = self.files.get(file_id)
        if row is None or row["tenant_id"] != tenant_id or row["owner_user_id"] != user_id:
            raise NotFoundError()
        row["status"] = "deleted"
        self.blobs.pop(file_id, None)

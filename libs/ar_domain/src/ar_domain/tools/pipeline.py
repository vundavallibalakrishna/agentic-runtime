"""Tool-call execution pipeline. Spec: docs/03-specs/08-tool-registry-mcp.md §5.

The policy step is an interface. The interim decider allows R0, R1 and W1.
"""

import time
import uuid
from dataclasses import dataclass
from typing import Any, Protocol

from ar_common.errors import QuotaExceededError
from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_common.wrapping import wrap_tool_result
from ar_domain.tools.credentials import CredentialBook
from ar_domain.tools.handlers import dispatch
from ar_domain.tools.logic import (
    as_int,
    as_mapping,
    call_args_hash,
    clearance_allows,
    interim_decision,
    preview,
    redact,
    schema_errors,
)
from ar_domain.tools.remote_mcp import RemoteError, call_remote
from ar_domain.usage.logic import UsageRecord
from ar_domain.usage.service import UsageBook, note

_IMPLICIT = frozenset(
    {
        "files.read",
        "files.list",
        "control.plan_update",
        "control.search",
        "plan.update",
        "tools.search",
    }
)


class PolicyDecider(Protocol):
    def decide(self, risk_class: str) -> tuple[str, str]:
        """Return ``(decision, message)``."""


@dataclass
class InterimPolicy:
    """Replaced by OPA in M5-T03."""

    def decide(self, risk_class: str) -> tuple[str, str]:
        return interim_decision(risk_class)


class ToolPipeline:
    def __init__(self, store: Any, policy: PolicyDecider | None = None) -> None:
        self.store = store
        self.policy = policy

    def resolve_catalog(
        self, *, agent_version_id: uuid.UUID, user_id: uuid.UUID, query: str = ""
    ) -> dict[str, object]:
        version = self.store.versions.get(agent_version_id)
        definition = version.get("definition") if isinstance(version, dict) else {}
        if not isinstance(definition, dict):
            definition = {}
        bindings = definition.get("tools")
        if not isinstance(bindings, list):
            bindings = []
        tools = []
        for binding in bindings:
            if not isinstance(binding, dict):
                continue
            server_slug = str(binding.get("server") or "")
            include = binding.get("include")
            names = include if isinstance(include, list) else ["*"]
            tools.extend(self._bound(server_slug, names, user_id))
        active = len(tools) > 30 or _search_mode(definition) == "on"
        if active and query:
            tools = _rank(tools, query)
        return {"tools": tools, "tool_search_active": active or len(tools) > 30}

    def execute(  # noqa: PLR0911, PLR0912, PLR0915
        self, request: dict[str, object]
    ) -> dict[str, object]:
        started = time.perf_counter()
        version = self.store.tool_versions.get(request.get("tool_version_id"))
        if not isinstance(version, dict):
            return self._fail(request, "not_found", "tool version was not found", started)
        tool = self.store.tool_defs.get(version.get("tool_id"))
        server_version = self.store.tool_server_versions.get(version.get("tool_server_version_id"))
        server = (
            self.store.tool_servers.get(tool.get("tool_server_id"))
            if isinstance(tool, dict)
            else None
        )
        if (
            not isinstance(tool, dict)
            or not isinstance(server, dict)
            or not isinstance(server_version, dict)
        ):
            return self._fail(request, "not_found", "tool version was not found", started)
        if server.get("disabled_at") is not None or tool.get("disabled_at") is not None:
            return self._fail(
                request, "tool_disabled", "this tool is disabled", started, version, tool
            )
        if not self._entitled(request, version):
            return self._fail(
                request, "not_entitled", "this run cannot call that tool", started, version, tool
            )
        limited = self._limited(request, tool, version)
        if limited is not None:
            return limited
        blocked = self._quota(request, version, tool, started)
        if blocked is not None:
            return blocked
        arguments = as_mapping(request.get("arguments"))
        schema = as_mapping(version.get("input_schema"))
        invalid = schema_errors(schema, arguments)
        if invalid:
            return self._fail(
                request, "validation_failed", invalid, started, version, tool, policy=False
            )
        expected = call_args_hash(str(version["id"]), arguments)
        supplied = str(request.get("args_hash") or expected)
        if supplied != expected:
            return self._fail(
                request,
                "validation_failed",
                "args_hash does not match",
                started,
                version,
                tool,
                policy=False,
            )
        if self._drifted(server, server_version):
            return self._fail(
                request,
                "tool_manifest_drift",
                "the server manifest changed",
                started,
                version,
                tool,
            )
        held = self._gate(request, version, tool, server, arguments, started)
        if held is not None:
            return held
        token = ""
        if server_version.get("auth_mode") == "user_oauth":
            token = self._token(request, server_version)
            if not token:
                connect = f"/connections?provider={self._provider_slug(server_version)}"
                return self._fail(
                    request,
                    "credential_required",
                    "Connect an account to use this tool.",
                    started,
                    version,
                    tool,
                    extra={"connect_url": connect},
                )
        endpoint = str(server_version.get("endpoint_url") or "")
        arguments = dict(arguments)
        if str(version.get("name")) in {"plan_update", "update"}:
            run = (
                self.store.runs.get(request.get("run_id"))
                if isinstance(request.get("run_id"), uuid.UUID)
                else None
            )
            if isinstance(run, dict) and isinstance(run.get("conversation_id"), uuid.UUID):
                arguments["conversation_id"] = run["conversation_id"]
        call_args = dict(arguments)
        if endpoint.startswith("builtin://"):
            call_args.update(self._sandbox_context(request))
        if endpoint.startswith(("https://", "http://")):
            try:
                outcome = call_remote(
                    self.store,
                    endpoint,
                    str(version.get("name")),
                    call_args,
                    token,
                    str(server_version.get("auth_mode") or "none"),
                )
            except RemoteError as exc:
                outcome = {
                    "text": exc.reason,
                    "structured": {},
                    "is_error": True,
                    "code": "upstream_error",
                }
        else:
            outcome = dispatch(self.store, endpoint, str(version.get("name")), call_args, token)
        self._emit_streams(request, outcome)
        plain = str(outcome.get("text") or "")
        from ar_domain.security.guardrails import apply_result_safety  # noqa: PLC0415

        plain, flag = apply_result_safety(
            self.store,
            plain,
            open_world=str(endpoint).startswith(("http://", "https://", "builtin://web")),
        )
        if flag.get("suspected"):
            outcome["injection_suspected"] = True
        wrapped = wrap_tool_result(
            tool=str(version.get("qualified_name")),
            call_id=str(request.get("model_call_id") or "call"),
            content=plain,
        )
        text = plain
        status = "failed" if outcome.get("is_error") else "succeeded"
        code = str(outcome.get("code") or "upstream_error")
        error: dict[str, object] | None = (
            {"code": code, "message": text} if outcome.get("is_error") else None
        )
        if status == "succeeded" and str(version.get("name")) in {"plan_update", "update"}:
            self._plan_event(request, outcome.get("structured"))
        stored = self._stored(
            request,
            version,
            tool,
            status,
            "allow",
            text,
            bool(outcome.get("is_error")),
            started,
            error,
            structured=outcome.get("structured"),
        )
        stored["wrapped"] = wrapped
        return stored

    def _sandbox_context(self, request: dict[str, object]) -> dict[str, object]:
        context: dict[str, object] = {
            "_tenant_id": request.get("tenant_id"),
            "_user_id": request.get("user_id"),
            "_agent_id": request.get("agent_id"),
            "_agent_version_id": request.get("agent_version_id"),
            "_run_id": request.get("run_id"),
            "_tool_call_id": request.get("model_call_id"),
        }
        run_id = request.get("run_id")
        run = self.store.runs.get(run_id) if isinstance(run_id, uuid.UUID) else None
        if not isinstance(run, dict):
            return context
        context["_conversation_id"] = run.get("conversation_id")
        if context.get("_agent_id") is None:
            context["_agent_id"] = run.get("agent_id")
        message = self.store.messages.get(run.get("input_message_id"))
        if isinstance(message, dict) and isinstance(message.get("attachment_ids"), list):
            context["_attachment_ids"] = message.get("attachment_ids")
        return context

    def _emit_streams(self, request: dict[str, object], outcome: dict[str, object]) -> None:
        streams = outcome.get("streams")
        if not isinstance(streams, list) or not hasattr(self.store, "_emit"):
            return
        run_id = request.get("run_id")
        run = self.store.runs.get(run_id) if isinstance(run_id, uuid.UUID) else None
        if not isinstance(run, dict):
            return
        call_id = request.get("tool_call_id")
        if not isinstance(call_id, uuid.UUID):
            call_id = new_id()
        for item in streams:
            if not isinstance(item, dict):
                continue
            stream = item.get("stream")
            text = str(item.get("text") or "")
            if stream not in {"stdout", "stderr"} or not text:
                continue
            self.store._emit(
                run,
                "sandbox.output",
                {"tool_call_id": str(call_id), "stream": stream, "text": text[:4000]},
            )

    def _gate(  # noqa: PLR0917
        self,
        request: dict[str, object],
        version: dict[str, object],
        tool: dict[str, object],
        server: dict[str, object],
        arguments: dict[str, object],
        started: float,
    ) -> dict[str, object] | None:
        """Return a finished result, or None when the call may execute."""
        risk = str(version.get("risk_class") or "")
        if request.get("approval_id"):
            from ar_domain.policy.engine import consume_granted  # noqa: PLC0415

            problem = consume_granted(self.store, request)
            if problem:
                return self._fail(
                    request,
                    "approval_invalid",
                    problem,
                    started,
                    version,
                    tool,
                    decision="deny",
                )
            return None
        outcome: dict[str, object]
        if self.policy is not None:
            decision, message = self.policy.decide(risk)
            outcome = {
                "decision": decision,
                "reasons": [message] if message else [],
                "approval": None,
            }
        else:
            from ar_domain.policy.engine import evaluate_call  # noqa: PLC0415

            outcome = evaluate_call(self.store, request, version, tool, server)
        decision = str(outcome.get("decision") or "deny")
        if decision == "allow":
            return None
        if request.get("dry_run") is True and risk in {"W2", "W3"}:
            return self._stored(
                request,
                version,
                tool,
                "succeeded",
                decision,
                "dry run",
                False,
                started,
                {"code": "dry_run"},
            )
        reasons = outcome.get("reasons")
        message = reasons[0] if isinstance(reasons, list) and reasons else "denied by policy"
        if decision == "require_approval":
            return self._hold(request, version, tool, arguments, started, outcome, str(message))
        return self._fail(
            request,
            "policy_denied",
            str(message),
            started,
            version,
            tool,
            decision="deny",
        )

    def _hold(  # noqa: PLR0917
        self,
        request: dict[str, object],
        version: dict[str, object],
        tool: dict[str, object],
        arguments: dict[str, object],
        started: float,
        outcome: dict[str, object],
        message: str,
    ) -> dict[str, object]:
        from ar_domain.approvals.logic import render_preview  # noqa: PLC0415
        from ar_domain.approvals.service import ApprovalBook  # noqa: PLC0415
        from ar_domain.policy.metrics import APPROVALS_CREATED  # noqa: PLC0415

        stored = self._stored(
            request,
            version,
            tool,
            "awaiting_approval",
            "require_approval",
            message,
            False,
            started,
            None,
        )
        call_id = uuid.UUID(str(stored["tool_call_id"]))
        requirement = outcome.get("approval")
        if not isinstance(requirement, dict):
            requirement = {}
        reasons = outcome.get("reasons")
        preview = render_preview(
            version.get("approval_preview"),
            arguments,
            title=str(version.get("title") or version.get("qualified_name")),
        )
        tenant_id = request.get("tenant_id")
        user_id = request.get("user_id")
        run_raw = request.get("run_id")
        agent_raw = request.get("agent_id")
        approval = ApprovalBook(self.store).create_pending(
            tenant_id=tenant_id if isinstance(tenant_id, uuid.UUID) else uuid.UUID(str(tenant_id)),
            user_id=user_id if isinstance(user_id, uuid.UUID) else uuid.UUID(str(user_id)),
            run_id=run_raw if isinstance(run_raw, uuid.UUID) else None,
            agent_id=agent_raw if isinstance(agent_raw, uuid.UUID) else None,
            tool_call_id=call_id,
            qualified_name=str(version.get("qualified_name")),
            risk_class=str(version.get("risk_class")),
            args_hash=str(request.get("args_hash") or ""),
            arguments=arguments,
            requirement=requirement,
            reasons=[str(item) for item in reasons] if isinstance(reasons, list) else [message],
            preview=preview,
        )
        row = self.store.tool_calls.get(call_id)
        if isinstance(row, dict):
            row["approval_id"] = approval["id"]
        APPROVALS_CREATED.labels(risk=str(version.get("risk_class"))).inc()
        stored["approval_id"] = str(approval["id"])
        stored["approval"] = ApprovalBook(self.store).summary(approval)
        stored["result_preview"] = "Waiting for approval."
        return stored

    def _bound(self, slug: str, names: list[object], user_id: uuid.UUID) -> list[dict[str, object]]:
        server = next(
            (
                row
                for row in self.store.tool_servers.values()
                if row.get("slug") == slug and row.get("status") == "approved"
            ),
            None,
        )
        if not isinstance(server, dict) or server.get("disabled_at") is not None:
            return []
        current = server.get("current_version_id")
        rows = []
        for version in self.store.tool_versions.values():
            if version.get("tool_server_version_id") != current:
                continue
            if "*" not in names and version.get("name") not in names:
                continue
            tool = self.store.tool_defs.get(version.get("tool_id"))
            if isinstance(tool, dict) and tool.get("disabled_at") is not None:
                continue
            if not clearance_allows(
                str(version.get("data_classification") or "internal"), "confidential"
            ):
                continue
            rows.append(
                {
                    "model_name": str(version.get("qualified_name")).replace(".", "__"),
                    "tool_version_id": str(version["id"]),
                    "qualified_name": version.get("qualified_name"),
                    "description": version.get("description"),
                    "parameters": version.get("input_schema"),
                    "risk_class": version.get("risk_class"),
                }
            )
        del user_id
        return rows

    def _entitled(self, request: dict[str, object], version: dict[str, object]) -> bool:
        if request.get("synthetic") is True:
            return True
        qualified = str(version.get("qualified_name"))
        if (
            qualified in _IMPLICIT
            or qualified.startswith("files.")
            or qualified.startswith("control.")
        ):
            return True
        agent_version_id = request.get("agent_version_id")
        version_row = (
            self.store.versions.get(agent_version_id)
            if isinstance(agent_version_id, uuid.UUID)
            else None
        )
        definition = version_row.get("definition") if isinstance(version_row, dict) else None
        tools = definition.get("tools") if isinstance(definition, dict) else None
        server_slug = qualified.split(".", 1)[0]
        if not isinstance(tools, list):
            return False
        return any(isinstance(item, dict) and item.get("server") == server_slug for item in tools)

    def _quota(
        self,
        request: dict[str, object],
        version: dict[str, object],
        tool: dict[str, object],
        started: float,
    ) -> dict[str, object] | None:
        tenant = request.get("tenant_id")
        if not isinstance(tenant, uuid.UUID):
            return None
        try:
            UsageBook(self.store).assert_tool(
                tenant, request.get("user_id"), request.get("agent_id")
            )
        except QuotaExceededError as exc:
            return self._fail(
                request, "quota_exceeded", str(exc), started, version, tool, policy=False
            )
        return None

    def _limited(
        self, request: dict[str, object], tool: dict[str, object], version: dict[str, object]
    ) -> dict[str, object] | None:
        cap = as_int(version.get("rate_limit_per_minute"), 60)
        key = f"{request.get('tenant_id')}:{tool.get('id')}"
        bucket: list[float] = self.store.rate_buckets.setdefault(key, [])
        now = time.time()
        fresh = [stamp for stamp in bucket if now - stamp < 60]
        if len(fresh) >= cap:
            self.store.rate_buckets[key] = fresh
            return self._fail(
                request,
                "tool_rate_limited",
                "this tool is rate limited",
                time.perf_counter(),
                version,
                tool,
            )
        fresh.append(now)
        self.store.rate_buckets[key] = fresh
        return None

    def _drifted(self, server: dict[str, object], version: dict[str, object]) -> bool:
        if server.get("kind") != "remote_mcp":
            return False
        if server.get("status") == "pending_review" and version.get("review_status") == "approved":
            return True
        upstream = str(version.get("upstream_hash") or version.get("manifest_hash") or "")
        return bool(upstream) and upstream != str(version.get("manifest_hash") or "")

    def _token(self, request: dict[str, object], server_version: dict[str, object]) -> str:
        provider_id = server_version.get("credential_provider_id")
        user_id = request.get("user_id")
        tenant_id = request.get("tenant_id")
        if (
            not isinstance(provider_id, uuid.UUID)
            or not isinstance(user_id, uuid.UUID)
            or not isinstance(tenant_id, uuid.UUID)
        ):
            return ""
        from ar_domain.agents.access import Actor  # noqa: PLC0415
        from ar_domain.identity.permissions import PERMISSION_KEYS  # noqa: PLC0415

        actor = Actor(tenant_id, user_id, PERMISSION_KEYS)
        import asyncio  # noqa: PLC0415

        book = CredentialBook(self.store)
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(book.access_token_for(actor, provider_id))
        return self._mint_from_grant(user_id, provider_id)

    def _mint_from_grant(self, user_id: uuid.UUID, provider_id: uuid.UUID) -> str:
        """Mint while an event loop is already running in this thread."""
        grant = next(
            (
                row
                for row in self.store.credential_grants.values()
                if row.get("user_id") == user_id
                and row.get("provider_id") == provider_id
                and row.get("status") == "active"
            ),
            None,
        )
        if not isinstance(grant, dict):
            return ""
        refresh = str(grant.get("refresh_token") or "")
        rotated = f"refresh-rotated-{refresh[-6:]}"
        grant["refresh_token"] = rotated
        grant["access_token"] = f"access-{rotated}"
        return str(grant["access_token"])

    def _plan_event(self, request: dict[str, object], structured: object) -> None:
        run_id = request.get("run_id")
        if not isinstance(run_id, uuid.UUID):
            return
        run = self.store.runs.get(run_id)
        if not isinstance(run, dict) or not hasattr(self.store, "_emit"):
            return
        plan = structured.get("plan") if isinstance(structured, dict) else []
        self.store._emit(run, "plan.updated", {"plan": plan if isinstance(plan, list) else []})

    def _provider_slug(self, server_version: dict[str, object]) -> str:
        provider = self.store.credential_providers.get(server_version.get("credential_provider_id"))
        if isinstance(provider, dict):
            return str(provider.get("slug") or "")
        return ""

    def _fail(  # noqa: PLR0917
        self,
        request: dict[str, object],
        code: str,
        message: str,
        started: float,
        version: dict[str, object] | None = None,
        tool: dict[str, object] | None = None,
        *,
        decision: str = "deny",
        policy: bool = True,
        extra: dict[str, object] | None = None,
    ) -> dict[str, object]:
        error: dict[str, object] = {"code": code, "message": message}
        if extra:
            error.update(extra)
        if code == "credential_required":
            notes = getattr(self.store, "notifications", None)
            if isinstance(notes, list):
                notes.append(
                    {
                        "kind": "credential_required",
                        "tenant_id": str(request.get("tenant_id")),
                        "user_id": str(request.get("user_id")),
                        "connect_url": extra.get("connect_url") if extra else None,
                    }
                )
        if version is None or tool is None or (policy is False and code == "validation_failed"):
            return {
                "status": "failed",
                "is_error": True,
                "error": error,
                "result_preview": message,
                "policy": {"decision": None if not policy else decision},
            }
        return self._stored(
            request,
            version,
            tool,
            "denied" if code == "policy_denied" else "failed",
            decision if policy else "allow",
            message,
            True,
            started,
            error,
        )

    def _stored(  # noqa: PLR0917
        self,
        request: dict[str, object],
        version: dict[str, object],
        tool: dict[str, object],
        status: str,
        decision: str,
        text: str,
        is_error: bool,  # noqa: FBT001
        started: float,
        error: dict[str, object] | None,
        structured: object = None,
    ) -> dict[str, object]:
        latency = int((time.perf_counter() - started) * 1000)
        arguments = as_mapping(request.get("arguments"))
        existing = request.get("tool_call_id")
        call_id = existing if isinstance(existing, uuid.UUID) else new_id()
        row = {
            "id": call_id,
            "tenant_id": request.get("tenant_id"),
            "run_id": request.get("run_id"),
            "tool_id": tool.get("id"),
            "tool_version_id": version.get("id"),
            "qualified_name": version.get("qualified_name"),
            "model_call_id": str(request.get("model_call_id") or call_id),
            "arguments_redacted": redact(arguments),
            "args_hash": str(request.get("args_hash") or ""),
            "risk_class": version.get("risk_class"),
            "policy_decision": decision,
            "policy_reasons": []
            if decision == "allow"
            else [str((error or {}).get("message") or "")],
            "status": status,
            "idempotency_key": f"{request.get('run_id')}:{request.get('model_call_id')}",
            "result_preview": preview(text),
            "is_error": is_error,
            "error": error,
            "latency_ms": latency,
            "created_at": utcnow(),
        }
        self.store.tool_calls[call_id] = row
        if status in {"succeeded", "failed", "denied"} and isinstance(
            request.get("tenant_id"), uuid.UUID
        ):
            note(
                self.store,
                UsageRecord(
                    str(request["tenant_id"]),
                    utcnow(),
                    "tool_calls",
                    1,
                    0,
                    f"tool:{call_id}",
                    user_id=None
                    if not isinstance(request.get("user_id"), uuid.UUID)
                    else str(request.get("user_id")),
                    agent_id=None
                    if not isinstance(request.get("agent_id"), uuid.UUID)
                    else str(request.get("agent_id")),
                    source="mcp-gateway",
                ),
            )
        risk = str(version.get("risk_class"))
        if risk in {"W1", "W2", "W3"} or status == "denied":
            self.store.audit_log.append(
                {
                    "tenant_id": str(request.get("tenant_id")),
                    "actor_id": str(request.get("user_id")),
                    "action": "tool.denied" if status == "denied" else "tool.called",
                    "target_type": "tool_call",
                    "target_id": str(call_id),
                    "detail": {"args_hash": row["args_hash"], "risk_class": risk},
                    "outcome": "success" if status == "succeeded" else "failure",
                    "at": utcnow().isoformat(),
                }
            )
        return {
            "status": status,
            "is_error": is_error,
            "result_preview": preview(text),
            "wrapped": text,
            "structured": structured if isinstance(structured, dict) else {},
            "error": error,
            "latency_ms": latency,
            "policy": {
                "decision": decision,
                "message": "" if decision == "allow" else str((error or {}).get("message") or ""),
            },
            "tool_call_id": str(call_id),
            "qualified_name": version.get("qualified_name"),
            "risk_class": risk,
            "arguments_redacted": row["arguments_redacted"],
        }


def _search_mode(definition: dict[str, object]) -> str:
    search = definition.get("tool_search")
    if isinstance(search, dict):
        return str(search.get("mode") or "auto")
    return "auto"


def _rank(tools: list[dict[str, object]], query: str) -> list[dict[str, object]]:
    from ar_domain.tools.logic import cosine, hash_embedding  # noqa: PLC0415

    vector = hash_embedding(query)
    scored = []
    for tool in tools:
        description = str(tool.get("description") or "")
        score = cosine(vector, hash_embedding(description))
        if query.lower() in description.lower():
            score += 0.5
        scored.append((score, tool))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [tool for _score, tool in scored[:12]]

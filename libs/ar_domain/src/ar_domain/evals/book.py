"""Evaluation suite catalogue. Spec: docs/03-specs/18-observability-eval.md §4.3."""

import uuid
from typing import TYPE_CHECKING, cast

import orjson
import yaml

from ar_common.errors import ArError, ErrorCode, NotFoundError, ValidationFailedError
from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_contracts.evals import parse_assertions, parse_gate, parse_input, parse_mocks
from ar_domain.audit.memory import remember
from ar_domain.evals.metrics import RUNS
from ar_domain.evals.runner import execute_eval_run

if TYPE_CHECKING:
    from typing import Any

    from ar_domain.agents.access import Actor

_KINDS = frozenset({"functional", "retrieval", "safety", "red_team"})
_TRIGGERS = frozenset({"manual", "publish_gate", "schedule", "ci"})


class EvalBook:
    """Suites, cases, runs and feedback for one process store."""

    def __init__(self, store: Any) -> None:
        self.store = store

    def ensure_platform(self, actor: Actor) -> int:
        """Install repository red-team and golden suites once per tenant."""
        from ar_domain.evals.seed_suites import install_platform  # noqa: PLC0415

        return install_platform(self, actor)

    def list_suites(
        self,
        actor: Actor,
        *,
        agent_id: uuid.UUID | None = None,
        kind: str | None = None,
    ) -> list[dict[str, object]]:
        self._need(actor, "evals:manage")
        rows = [
            self._suite_view(row)
            for row in self.store.eval_suites.values()
            if self._visible(row, actor.tenant_id)
            and (agent_id is None or row.get("agent_id") == agent_id)
            and (kind is None or row.get("kind") == kind)
        ]
        rows.sort(key=lambda item: str(item.get("name") or ""))
        return rows

    def create_suite(self, actor: Actor, body: dict[str, object]) -> dict[str, object]:
        self._need(actor, "evals:manage")
        name = str(body.get("name") or "").strip()
        if not name:
            raise ValidationFailedError("name is required")
        kind = str(body.get("kind") or "functional")
        if kind not in _KINDS:
            raise ValidationFailedError("kind is invalid")
        self._unique_name(actor.tenant_id, name, None)
        suite_id = new_id()
        now = utcnow()
        row: dict[str, object] = {
            "id": suite_id,
            "tenant_id": actor.tenant_id,
            "agent_id": _optional_uuid(body.get("agent_id")),
            "name": name,
            "description": str(body.get("description") or ""),
            "kind": kind,
            "gate": parse_gate(body.get("gate")),
            "created_by": actor.user_id,
            "created_at": now,
            "updated_at": now,
        }
        self.store.eval_suites[suite_id] = row
        self._audit(actor, "eval_suite.created", suite_id, {"name": name})
        return self._suite_view(row)

    def get_suite(self, actor: Actor, suite_id: uuid.UUID) -> dict[str, object]:
        self._need(actor, "evals:manage")
        return self._suite_view(self._suite(actor, suite_id))

    def update_suite(
        self, actor: Actor, suite_id: uuid.UUID, body: dict[str, object]
    ) -> dict[str, object]:
        self._need(actor, "evals:manage")
        row = self._suite(actor, suite_id)
        if "name" in body:
            name = str(body.get("name") or "").strip()
            if not name:
                raise ValidationFailedError("name is required")
            self._unique_name(actor.tenant_id, name, suite_id)
            row["name"] = name
        if "description" in body:
            row["description"] = str(body.get("description") or "")
        if "kind" in body:
            kind = str(body.get("kind") or "")
            if kind not in _KINDS:
                raise ValidationFailedError("kind is invalid")
            row["kind"] = kind
        if "gate" in body:
            row["gate"] = parse_gate(body.get("gate"))
        if "agent_id" in body:
            row["agent_id"] = _optional_uuid(body.get("agent_id"))
        row["updated_at"] = utcnow()
        self._audit(actor, "eval_suite.updated", suite_id, {"name": row["name"]})
        return self._suite_view(row)

    def delete_suite(self, actor: Actor, suite_id: uuid.UUID) -> None:
        self._need(actor, "evals:manage")
        row = self._suite(actor, suite_id)
        self.store.eval_suites.pop(suite_id, None)
        for case_id, case in list(self.store.eval_cases.items()):
            if isinstance(case, dict) and case.get("suite_id") == suite_id:
                self.store.eval_cases.pop(case_id, None)
        self._audit(actor, "eval_suite.deleted", suite_id, {"name": row.get("name")})

    def list_cases(self, actor: Actor, suite_id: uuid.UUID) -> list[dict[str, object]]:
        self._need(actor, "evals:manage")
        self._suite(actor, suite_id)
        rows = [
            self._case_view(case)
            for case in self.store.eval_cases.values()
            if isinstance(case, dict) and case.get("suite_id") == suite_id
        ]
        rows.sort(key=lambda item: str(item.get("name") or ""))
        return rows

    def create_case(
        self, actor: Actor, suite_id: uuid.UUID, body: dict[str, object]
    ) -> dict[str, object]:
        self._need(actor, "evals:manage")
        self._suite(actor, suite_id)
        return self._case_view(self._insert_case(actor, suite_id, body))

    def update_case(
        self, actor: Actor, suite_id: uuid.UUID, case_id: uuid.UUID, body: dict[str, object]
    ) -> dict[str, object]:
        self._need(actor, "evals:manage")
        self._suite(actor, suite_id)
        row = self._case(actor, case_id)
        if row.get("suite_id") != suite_id:
            raise NotFoundError()
        if "name" in body:
            row["name"] = str(body.get("name") or "").strip() or str(row.get("name"))
        if "input" in body:
            row["input"] = parse_input(body.get("input"))
        if "assertions" in body:
            row["assertions"] = parse_assertions(body.get("assertions"))
        if "tool_mocks" in body:
            row["tool_mocks"] = parse_mocks(body.get("tool_mocks"))
        if "tags" in body:
            row["tags"] = _tags(body.get("tags"))
        row["updated_at"] = utcnow()
        self._audit(actor, "eval_suite.updated", suite_id, {"case_id": str(case_id)})
        return self._case_view(row)

    def delete_case(self, actor: Actor, suite_id: uuid.UUID, case_id: uuid.UUID) -> None:
        self._need(actor, "evals:manage")
        self._suite(actor, suite_id)
        row = self._case(actor, case_id)
        if row.get("suite_id") != suite_id:
            raise NotFoundError()
        self.store.eval_cases.pop(case_id, None)
        self._audit(actor, "eval_suite.updated", suite_id, {"case_id": str(case_id)})

    def import_cases(
        self, actor: Actor, suite_id: uuid.UUID, file_id: uuid.UUID
    ) -> dict[str, object]:
        self._need(actor, "evals:manage")
        self._suite(actor, suite_id)
        file_row = self.store.files.get(file_id)
        if not isinstance(file_row, dict) or file_row.get("tenant_id") != actor.tenant_id:
            raise NotFoundError()
        if file_row.get("kind") != "eval_dataset":
            raise ValidationFailedError("file must be an eval dataset")
        blob = self.store.blobs.get(file_id, b"")
        text = blob.decode("utf-8", errors="replace") if isinstance(blob, bytes) else str(blob)
        return self._import_text(actor, suite_id, text)

    def case_from_conversation(
        self, actor: Actor, suite_id: uuid.UUID, body: dict[str, object]
    ) -> dict[str, object]:
        self._need(actor, "evals:manage")
        self._suite(actor, suite_id)
        conversation_id = _required_uuid(body.get("conversation_id"), "conversation_id")
        message_id = _required_uuid(body.get("message_id"), "message_id")
        conversation = self.store.conversations.get(conversation_id)
        if not isinstance(conversation, dict) or conversation.get("tenant_id") != actor.tenant_id:
            raise NotFoundError()
        turns = _user_turns(self.store, conversation_id, message_id)
        if not turns:
            raise ValidationFailedError("conversation has no user turns")
        comment = _feedback_comment(self.store, message_id)
        assertions = body.get("assertions")
        if not isinstance(assertions, list) or not assertions:
            assertions = [
                {
                    "type": "llm_judge",
                    "rubric": comment or "The answer should address the user's request.",
                    "threshold": 0.5,
                }
            ]
        return self._case_view(
            self._insert_case(
                actor,
                suite_id,
                {
                    "name": str(body.get("name") or "From conversation"),
                    "input": {"messages": turns},
                    "assertions": assertions,
                    "tags": body.get("tags") or ["feedback"],
                },
            )
        )

    def start_run(
        self, actor: Actor, suite_id: uuid.UUID, body: dict[str, object]
    ) -> dict[str, object]:
        self._need(actor, "evals:run")
        suite = self._suite(actor, suite_id)
        agent_id = _optional_uuid(body.get("agent_id")) or suite.get("agent_id")
        if not isinstance(agent_id, uuid.UUID):
            agent_id = _default_agent(self.store, actor.tenant_id)
        version_id = _resolve_version(
            self.store, agent_id, body.get("agent_version_ref") or "published"
        )
        trigger = str(body.get("trigger") or "manual")
        if trigger not in _TRIGGERS:
            raise ValidationFailedError("trigger is invalid")
        if body.get("model_alias_override") and not actor.has("evals:manage"):
            raise ArError(ErrorCode.FORBIDDEN, "model override requires evals:manage")
        run_id = new_id()
        now = utcnow()
        row = {
            "id": run_id,
            "tenant_id": actor.tenant_id,
            "suite_id": suite_id,
            "agent_id": agent_id,
            "agent_version_id": version_id,
            "model_alias_override": body.get("model_alias_override"),
            "status": "queued",
            "summary": {},
            "baseline_eval_run_id": _optional_uuid(body.get("baseline_eval_run_id")),
            "temporal_workflow_id": f"eval-{run_id}",
            "triggered_by": actor.user_id,
            "trigger": trigger,
            "tags": _tags(body.get("tags")),
            "mock_all_tools": bool(body.get("mock_all_tools")),
            "change_note": str(body.get("change_note") or ""),
            "started_at": None,
            "finished_at": None,
            "created_at": now,
        }
        self.store.eval_runs[run_id] = row
        self._audit(actor, "eval_run.started", run_id, {"suite_id": str(suite_id)})
        RUNS.labels(status="queued", trigger=trigger).inc()
        if _inline(self.store):
            execute_eval_run(self.store, run_id)
        stored = self.store.eval_runs.get(run_id)
        return self._run_view(stored if isinstance(stored, dict) else row)

    def list_runs(
        self,
        actor: Actor,
        *,
        suite_id: uuid.UUID | None = None,
        agent_id: uuid.UUID | None = None,
        status: str | None = None,
    ) -> list[dict[str, object]]:
        self._need(actor, "evals:manage")
        rows = [
            self._run_view(row)
            for row in self.store.eval_runs.values()
            if self._visible(row, actor.tenant_id)
            and (suite_id is None or row.get("suite_id") == suite_id)
            and (agent_id is None or row.get("agent_id") == agent_id)
            and (status is None or row.get("status") == status)
        ]
        rows.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
        return rows

    def get_run(self, actor: Actor, eval_run_id: uuid.UUID) -> dict[str, object]:
        self._need(actor, "evals:manage")
        return self._run_view(self._run(actor, eval_run_id))

    def results(self, actor: Actor, eval_run_id: uuid.UUID) -> list[dict[str, object]]:
        self._need(actor, "evals:manage")
        self._run(actor, eval_run_id)
        found: list[dict[str, object]] = []
        for row in self.store.eval_results.values():
            if not isinstance(row, dict) or row.get("eval_run_id") != eval_run_id:
                continue
            case = self.store.eval_cases.get(row.get("case_id"))
            found.append(
                {
                    "case": {
                        "id": row.get("case_id"),
                        "name": case.get("name") if isinstance(case, dict) else "",
                        "tags": list(case.get("tags") or []) if isinstance(case, dict) else [],
                    },
                    "passed": bool(row.get("passed")),
                    "scores": row.get("scores") or {},
                    "output_text": row.get("output_text") or "",
                    "latency_ms": row.get("latency_ms"),
                    "cost_micros": row.get("cost_micros") or 0,
                    "run_id": row.get("run_id"),
                }
            )
        return found

    def cancel(self, actor: Actor, eval_run_id: uuid.UUID) -> dict[str, object]:
        self._need(actor, "evals:manage")
        row = self._run(actor, eval_run_id)
        if row.get("status") in {"completed", "failed", "cancelled"}:
            raise ArError(ErrorCode.INVALID_STATE, "eval run is already finished")
        row["status"] = "cancelled"
        row["finished_at"] = utcnow()
        self._audit(actor, "eval_run.cancelled", eval_run_id, {})
        RUNS.labels(status="cancelled", trigger=str(row.get("trigger") or "manual")).inc()
        return self._run_view(row)

    def list_feedback(self, actor: Actor) -> list[dict[str, object]]:
        self._need(actor, "evals:manage")
        rows: list[dict[str, object]] = []
        for row in self.store.feedback.values():
            if not isinstance(row, dict) or row.get("tenant_id") != actor.tenant_id:
                continue
            message_id = row.get("message_id")
            message = (
                self.store.messages.get(message_id) if isinstance(message_id, uuid.UUID) else None
            )
            conversation_id = message.get("conversation_id") if isinstance(message, dict) else None
            conversation = (
                self.store.conversations.get(conversation_id)
                if isinstance(conversation_id, uuid.UUID)
                else None
            )
            agent = _agent_ref(self.store, conversation)
            visible = _can_read_conversation(conversation, actor)
            rows.append(
                {
                    "message_id": message_id,
                    "conversation_id": conversation_id,
                    "agent": agent,
                    "rating": row.get("rating"),
                    "reasons": row.get("reasons") or [],
                    "comment": row.get("comment") if visible else "",
                    "created_at": row.get("created_at"),
                }
            )
        rows.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
        return rows

    def gated_suite_ids(self, actor: Actor, agent_id: uuid.UUID) -> list[uuid.UUID]:
        """Suites for this agent whose gate is required."""
        found: list[uuid.UUID] = []
        for row in self.store.eval_suites.values():
            if not isinstance(row, dict) or row.get("tenant_id") != actor.tenant_id:
                continue
            if row.get("agent_id") != agent_id:
                continue
            gate = row.get("gate")
            if (
                isinstance(gate, dict)
                and gate.get("required")
                and isinstance(row.get("id"), uuid.UUID)
            ):
                found.append(row["id"])
        return found

    def _import_text(self, actor: Actor, suite_id: uuid.UUID, text: str) -> dict[str, object]:
        imported = 0
        errors: list[dict[str, object]] = []
        documents, numbered = _documents(text)
        for line, document in numbered:
            if "_error" in document:
                errors.append({"line": line, "msg": str(document["_error"])})
                continue
            try:
                self._insert_case(actor, suite_id, document)
            except (ValidationFailedError, ArError) as exc:
                errors.append({"line": line, "msg": str(exc)})
                continue
            imported += 1
        if not documents and not errors:
            errors.append({"line": 1, "msg": "dataset is empty"})
        return {"imported": imported, "errors": errors}

    def _insert_case(
        self, actor: Actor, suite_id: uuid.UUID, body: dict[str, object]
    ) -> dict[str, object]:
        name = str(body.get("name") or "").strip()
        if not name:
            raise ValidationFailedError("name is required")
        case_id = new_id()
        now = utcnow()
        row = {
            "id": case_id,
            "tenant_id": actor.tenant_id,
            "suite_id": suite_id,
            "name": name,
            "input": parse_input(body.get("input")),
            "assertions": parse_assertions(body.get("assertions")),
            "tool_mocks": parse_mocks(body.get("tool_mocks")),
            "tags": _tags(body.get("tags")),
            "created_at": now,
            "updated_at": now,
        }
        self.store.eval_cases[case_id] = row
        return row

    def _suite(self, actor: Actor, suite_id: uuid.UUID) -> dict[str, object]:
        row = self.store.eval_suites.get(suite_id)
        if not isinstance(row, dict) or row.get("tenant_id") != actor.tenant_id:
            raise NotFoundError()
        return row

    def _case(self, actor: Actor, case_id: uuid.UUID) -> dict[str, object]:
        row = self.store.eval_cases.get(case_id)
        if not isinstance(row, dict) or row.get("tenant_id") != actor.tenant_id:
            raise NotFoundError()
        return row

    def _run(self, actor: Actor, eval_run_id: uuid.UUID) -> dict[str, object]:
        row = self.store.eval_runs.get(eval_run_id)
        if not isinstance(row, dict) or row.get("tenant_id") != actor.tenant_id:
            raise NotFoundError()
        return row

    def _suite_view(self, row: dict[str, object]) -> dict[str, object]:
        suite_id = row.get("id")
        cases = [
            case
            for case in self.store.eval_cases.values()
            if isinstance(case, dict) and case.get("suite_id") == suite_id
        ]
        last = _last_run(self.store, suite_id)
        return {
            "id": suite_id,
            "name": row.get("name"),
            "description": row.get("description") or "",
            "kind": row.get("kind"),
            "agent": _agent_ref(self.store, {"agent_id": row.get("agent_id")}),
            "gate": row.get("gate") or {},
            "case_count": len(cases),
            "last_run": last,
        }

    def _case_view(self, row: dict[str, object]) -> dict[str, object]:
        return {
            "id": row.get("id"),
            "suite_id": row.get("suite_id"),
            "name": row.get("name"),
            "input": row.get("input"),
            "assertions": row.get("assertions"),
            "tool_mocks": row.get("tool_mocks") or [],
            "tags": _string_list(row.get("tags")),
        }

    def _run_view(self, row: dict[str, object]) -> dict[str, object]:
        return {
            "id": row.get("id"),
            "suite_id": row.get("suite_id"),
            "agent_id": row.get("agent_id"),
            "agent_version_id": row.get("agent_version_id"),
            "model_alias_override": row.get("model_alias_override"),
            "status": row.get("status"),
            "summary": row.get("summary") or {},
            "baseline_eval_run_id": row.get("baseline_eval_run_id"),
            "temporal_workflow_id": row.get("temporal_workflow_id"),
            "triggered_by": row.get("triggered_by"),
            "trigger": row.get("trigger"),
            "started_at": row.get("started_at"),
            "finished_at": row.get("finished_at"),
            "created_at": row.get("created_at"),
        }

    def _unique_name(self, tenant_id: uuid.UUID, name: str, current: uuid.UUID | None) -> None:
        for row in self.store.eval_suites.values():
            if not isinstance(row, dict) or row.get("tenant_id") != tenant_id:
                continue
            if row.get("name") == name and row.get("id") != current:
                raise ArError(ErrorCode.CONFLICT, "a suite with that name already exists")

    def _audit(
        self, actor: Actor, action: str, target: uuid.UUID, detail: dict[str, object]
    ) -> None:
        remember(
            self.store,
            tenant_id=actor.tenant_id,
            actor_id=actor.user_id,
            action=action,
            target_type="eval_suite" if action.startswith("eval_suite") else "eval_run",
            target_id=target,
            detail=detail,
        )

    @staticmethod
    def _need(actor: Actor, permission: str) -> None:
        if not actor.has(permission):
            raise ArError(ErrorCode.FORBIDDEN, "missing permission")

    @staticmethod
    def _visible(row: object, tenant_id: uuid.UUID) -> bool:
        return isinstance(row, dict) and row.get("tenant_id") == tenant_id


def _inline(store: Any) -> bool:
    """Score in this process unless a test is driving EvalRunWorkflow itself."""
    return not getattr(store, "defer_eval_runs", False)


def _optional_uuid(value: object) -> uuid.UUID | None:
    if value is None or value == "":
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except ValueError:
        raise ValidationFailedError("id is invalid") from None


def _required_uuid(value: object, label: str) -> uuid.UUID:
    parsed = _optional_uuid(value)
    if parsed is None:
        raise ValidationFailedError(f"{label} is required")
    return parsed


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _tags(value: object) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValidationFailedError("tags must be a list")
    return [str(item) for item in value]


def _documents(text: str) -> tuple[list[dict[str, object]], list[tuple[int, dict[str, object]]]]:
    stripped = text.strip()
    if not stripped:
        return [], []
    if (
        stripped.startswith("{")
        or stripped.startswith("[")
        or stripped.startswith("-")
        or ":" in stripped[:80]
    ):
        loaded = _yaml_documents(stripped)
        if loaded is not None:
            return loaded, list(enumerate(loaded, start=1))
    numbered: list[tuple[int, dict[str, object]]] = []
    documents: list[dict[str, object]] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = orjson.loads(line)
        except orjson.JSONDecodeError as exc:
            numbered.append((line_no, {"_error": str(exc)}))
            continue
        if isinstance(payload, dict):
            documents.append(payload)
            numbered.append((line_no, payload))
        else:
            numbered.append((line_no, {"_error": "each line must be an object"}))
    return documents, numbered


def _yaml_documents(text: str) -> list[dict[str, object]] | None:
    try:
        loaded = yaml.safe_load(text)
    except yaml.YAMLError:
        return None
    if isinstance(loaded, list):
        return [item for item in loaded if isinstance(item, dict)]
    if isinstance(loaded, dict) and isinstance(loaded.get("cases"), list):
        return [item for item in loaded["cases"] if isinstance(item, dict)]
    if isinstance(loaded, dict) and "input" in loaded:
        return [loaded]
    return None


def _user_turns(store: Any, conversation_id: uuid.UUID, message_id: uuid.UUID) -> list[str]:
    rows = [
        message
        for message in store.messages.values()
        if isinstance(message, dict) and message.get("conversation_id") == conversation_id
    ]
    rows.sort(key=lambda item: str(item.get("created_at") or ""))
    turns: list[str] = []
    seen = False
    for message in rows:
        if message.get("role") == "user":
            content = message.get("content")
            if isinstance(content, str):
                turns.append(content)
            elif isinstance(content, list):
                turns.append(" ".join(str(part) for part in content))
        if message.get("id") == message_id:
            seen = True
            break
    if not seen:
        raise NotFoundError()
    return turns


def _feedback_comment(store: Any, message_id: uuid.UUID) -> str:
    for row in store.feedback.values():
        if isinstance(row, dict) and row.get("message_id") == message_id:
            return str(row.get("comment") or "")
    return ""


def _agent_ref(store: Any, row: object) -> dict[str, object] | None:
    if not isinstance(row, dict):
        return None
    agent_id = row.get("agent_id")
    if not isinstance(agent_id, uuid.UUID):
        return None
    agent = store.agents.get(agent_id)
    name = agent.get("name") if isinstance(agent, dict) else ""
    return {"id": agent_id, "name": name}


def _can_read_conversation(conversation: object, actor: Actor) -> bool:
    if not isinstance(conversation, dict):
        return False
    if conversation.get("user_id") == actor.user_id:
        return True
    return actor.has("agents:manage_all")


def _last_run(store: Any, suite_id: object) -> dict[str, object] | None:
    latest: dict[str, object] | None = None
    for row in store.eval_runs.values():
        if not isinstance(row, dict) or row.get("suite_id") != suite_id:
            continue
        if latest is None or str(row.get("created_at") or "") >= str(
            latest.get("created_at") or ""
        ):
            latest = row
    if latest is None:
        return None
    summary = latest.get("summary") if isinstance(latest.get("summary"), dict) else {}
    rate = summary.get("pass_rate") if isinstance(summary, dict) else None
    return {
        "id": latest.get("id"),
        "pass_rate": rate,
        "status": latest.get("status"),
        "created_at": latest.get("created_at"),
    }


def _default_agent(store: Any, tenant_id: uuid.UUID) -> uuid.UUID:
    for agent in store.agents.values():
        if (
            isinstance(agent, dict)
            and agent.get("tenant_id") == tenant_id
            and agent.get("slug") == "assistant"
        ):
            found = agent.get("id")
            if isinstance(found, uuid.UUID):
                return found
    raise ValidationFailedError("agent_id is required")


def _resolve_version(store: Any, agent_id: uuid.UUID | None, ref: object) -> uuid.UUID | None:
    if not isinstance(agent_id, uuid.UUID):
        return None
    agent = store.agents.get(agent_id)
    if not isinstance(agent, dict):
        raise NotFoundError()
    if ref == "draft":
        draft = agent.get("draft_version_id") or agent.get("published_version_id")
        return draft if isinstance(draft, uuid.UUID) else None
    if isinstance(ref, int) or (isinstance(ref, str) and ref.isdigit()):
        number = int(ref)
        for version in store.versions.values():
            if (
                isinstance(version, dict)
                and version.get("agent_id") == agent_id
                and version.get("version") == number
            ):
                found = version.get("id")
                return found if isinstance(found, uuid.UUID) else None
        raise NotFoundError()
    published = agent.get("published_version_id") or agent.get("draft_version_id")
    return published if isinstance(published, uuid.UUID) else None


def public_row(row: dict[str, object]) -> dict[str, object]:
    """Stringify ids and timestamps for an HTTP response."""
    out: dict[str, object] = {}
    for key, value in row.items():
        out[key] = _public_value(value)
    return out


def _public_value(value: object) -> object:
    if isinstance(value, uuid.UUID):
        return str(value)
    if hasattr(value, "isoformat"):
        return cast("Any", value).isoformat()
    if isinstance(value, dict):
        return {str(key): _public_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_public_value(item) for item in value]
    return value

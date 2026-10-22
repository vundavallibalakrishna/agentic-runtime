"""Process-store memory. Postgres revision 0015 is the durable copy (OQ-39)."""

import time
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from typing import Any

from ar_common.errors import ForbiddenError, NotFoundError, ValidationFailedError
from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_domain.agents.access import Actor, can_edit
from ar_domain.audit.memory import remember
from ar_domain.knowledge.embedder import embed_texts
from ar_domain.memory.extract import extraction_input, heuristic_ops, parse_ops
from ar_domain.memory.format import memory_block
from ar_domain.memory.logic import (
    CONTENT_LIMIT,
    DEFAULT_TOP_K,
    MIN_CONFIDENCE,
    SHARED_FACT_LIMIT,
    TOKEN_BUDGET,
    USER_FACT_LIMIT,
    age_days,
    blocked_reason,
    category_of,
    dedupe_similarity,
    dimensions,
    estimate_fact_tokens,
    min_similarity,
    normalise,
    score,
    similarity,
)
from ar_domain.memory.metrics import (
    EXTRACTION_OPS,
    FACTS,
    PENDING_REVIEW,
    RECALL_SECONDS,
    RECALLED_FACTS,
)

_TRIGGERS = frozenset({"chat", "channel", "api"})
_STANDING = frozenset({"preference", "instruction"})


class MemoryBook:
    """Facts, recall and extraction for one process store."""

    def __init__(self, store: Any) -> None:
        self.store = store

    def list_user(
        self,
        actor: Actor,
        *,
        scope: str | None = None,
        agent_id: uuid.UUID | None = None,
        category: str | None = None,
        query: str = "",
        status: str = "active",
    ) -> list[dict[str, object]]:
        rows = [
            row
            for row in self._owned(actor)
            if _status_ok(row, status) and _scope_ok(row, scope) and _agent_ok(row, agent_id)
        ]
        rows = [row for row in rows if _category_ok(row, category)]
        rows = _search(rows, query)
        return [public_fact(self.store, row) for row in rows]

    def create_user(self, actor: Actor, body: dict[str, object]) -> dict[str, object]:
        scope = str(body.get("scope") or "user")
        if scope not in {"user", "agent_user"}:
            raise ValidationFailedError("scope must be user or agent_user")
        agent_id = _uuid(body.get("agent_id"))
        if scope == "agent_user" and agent_id is None:
            raise ValidationFailedError("agent_id is required for agent_user")
        if agent_id is not None:
            self._agent(actor, agent_id)
        content = _content(body.get("content"))
        self._guard(content, explicit=True)
        category = _category(body.get("category"))
        row = self._insert(
            actor,
            scope=scope,
            user_id=actor.user_id,
            agent_id=agent_id,
            team_id=None,
            content=content,
            category=category,
            source_kind="explicit",
            trust_level="high",
            confidence=1.0,
            status="active",
            source_ref={},
        )
        self._audit(actor, "memory.created", row["id"], {"scope": scope})
        return public_fact(self.store, row)

    def patch_user(
        self, actor: Actor, fact_id: uuid.UUID, body: dict[str, object]
    ) -> dict[str, object]:
        row = self._owned_row(actor, fact_id)
        self._rewrite(actor, row, body)
        self._audit(actor, "memory.updated", row["id"], {"scope": row["scope"]})
        return public_fact(self.store, row)

    def delete_user(self, actor: Actor, fact_id: uuid.UUID) -> None:
        row = self._owned_row(actor, fact_id)
        self._rows().pop(fact_id, None)
        self._audit(actor, "memory.deleted", row["id"], {"scope": row["scope"]})
        self._gauges()

    def forget_all(self, actor: Actor, *, agent_id: uuid.UUID | None, confirmed: bool) -> int:
        if not confirmed:
            raise ValidationFailedError("X-Confirm: delete-all-memory is required")
        doomed = [
            row for row in self._owned(actor) if agent_id is None or row.get("agent_id") == agent_id
        ]
        ids = [str(row["id"]) for row in doomed]
        for row in doomed:
            self._rows().pop(_uuid_key(row["id"]), None)
        self._audit(actor, "memory.cleared", actor.user_id, {"fact_ids": ids, "count": len(ids)})
        self._gauges()
        return len(ids)

    def set_enabled(self, actor: Actor, *, enabled: bool) -> dict[str, object]:
        settings = self.store.user_settings.setdefault(actor.user_id, {})
        if isinstance(settings, dict):
            settings["memory_enabled"] = enabled
        self._audit(actor, "memory.updated", actor.user_id, {"memory_enabled": enabled})
        return {"memory_enabled": enabled}

    def memory_enabled(self, actor: Actor) -> bool:
        return _user_enabled(self.store, actor.user_id)

    def visible_teams(self, actor: Actor) -> list[dict[str, object]]:
        """Teams the caller belongs to, with the facts they are allowed to read."""
        roster = getattr(self.store, "team_roster", {})
        if not isinstance(roster, dict):
            return []
        teams: list[dict[str, object]] = []
        for team_id in sorted(_team_ids(self.store, actor), key=str):
            team = roster.get(team_id)
            name = "Team"
            if isinstance(team, dict) and team.get("name"):
                name = str(team["name"])
            teams.append(
                {
                    "id": str(team_id),
                    "name": name,
                    "items": self.list_team(actor, team_id),
                }
            )
        return teams

    def list_agent(
        self, actor: Actor, agent_id: uuid.UUID, *, status: str | None = None
    ) -> list[dict[str, object]]:
        agent = self._agent(actor, agent_id)
        if not _can_review(actor, agent):
            raise ForbiddenError("memory:manage_agent is required")
        rows = [
            row
            for row in self._rows().values()
            if row.get("tenant_id") == actor.tenant_id
            and row.get("scope") == "agent"
            and row.get("agent_id") == agent_id
            and (status is None or row.get("status") == status)
        ]
        return [public_fact(self.store, row) for row in rows]

    def create_agent(
        self, actor: Actor, agent_id: uuid.UUID, body: dict[str, object]
    ) -> dict[str, object]:
        agent = self._agent(actor, agent_id)
        content = _content(body.get("content"))
        self._guard(content, explicit=True)
        category = _category(body.get("category") or "lesson")
        editor = _can_review(actor, agent)
        status = "active" if editor else "pending_review"
        source = "admin" if editor else "explicit"
        row = self._insert(
            actor,
            scope="agent",
            user_id=None,
            agent_id=agent_id,
            team_id=None,
            content=content,
            category=category,
            source_kind=source,
            trust_level="high",
            confidence=1.0,
            status=status,
            source_ref={},
        )
        self._audit(actor, "memory.created", row["id"], {"scope": "agent", "status": status})
        if not editor:
            self._propose(actor, row)
        return public_fact(self.store, row)

    def approve(self, actor: Actor, agent_id: uuid.UUID, fact_id: uuid.UUID) -> dict[str, object]:
        row = self._agent_row(actor, agent_id, fact_id)
        row["status"] = "active"
        row["updated_at"] = utcnow()
        self._audit(actor, "memory.approved", row["id"], {"scope": "agent"})
        self._gauges()
        return public_fact(self.store, row)

    def reject(self, actor: Actor, agent_id: uuid.UUID, fact_id: uuid.UUID) -> None:
        row = self._agent_row(actor, agent_id, fact_id)
        self._rows().pop(fact_id, None)
        self._audit(actor, "memory.rejected", row["id"], {"scope": "agent"})
        self._gauges()

    def patch_agent(
        self, actor: Actor, agent_id: uuid.UUID, fact_id: uuid.UUID, body: dict[str, object]
    ) -> dict[str, object]:
        row = self._agent_row(actor, agent_id, fact_id)
        self._rewrite(actor, row, body)
        self._audit(actor, "memory.updated", row["id"], {"scope": "agent"})
        return public_fact(self.store, row)

    def delete_agent(self, actor: Actor, agent_id: uuid.UUID, fact_id: uuid.UUID) -> None:
        row = self._agent_row(actor, agent_id, fact_id)
        self._rows().pop(fact_id, None)
        self._audit(actor, "memory.deleted", row["id"], {"scope": "agent"})
        self._gauges()

    def list_team(self, actor: Actor, team_id: uuid.UUID) -> list[dict[str, object]]:
        self._require_team(actor, team_id, write=False)
        rows = [
            row
            for row in self._rows().values()
            if row.get("tenant_id") == actor.tenant_id
            and row.get("scope") == "team"
            and row.get("team_id") == team_id
            and row.get("status") == "active"
        ]
        return [public_fact(self.store, row) for row in rows]

    def create_team(
        self, actor: Actor, team_id: uuid.UUID, body: dict[str, object]
    ) -> dict[str, object]:
        self._require_team(actor, team_id, write=True)
        content = _content(body.get("content"))
        self._guard(content, explicit=True)
        row = self._insert(
            actor,
            scope="team",
            user_id=None,
            agent_id=None,
            team_id=team_id,
            content=content,
            category=_category(body.get("category") or "glossary"),
            source_kind="admin",
            trust_level="high",
            confidence=1.0,
            status="active",
            source_ref={},
        )
        self._audit(actor, "memory.created", row["id"], {"scope": "team"})
        return public_fact(self.store, row)

    def delete_team(self, actor: Actor, team_id: uuid.UUID, fact_id: uuid.UUID) -> None:
        self._require_team(actor, team_id, write=True)
        row = self._rows().get(fact_id)
        if (
            not isinstance(row, dict)
            or row.get("tenant_id") != actor.tenant_id
            or row.get("team_id") != team_id
        ):
            raise NotFoundError("memory fact not found")
        self._rows().pop(fact_id, None)
        self._audit(actor, "memory.deleted", fact_id, {"scope": "team"})
        self._gauges()

    def recall(
        self,
        actor: Actor,
        *,
        query: str,
        agent_id: uuid.UUID | None,
        definition: dict[str, object],
        top_k: int | None = None,
    ) -> list[dict[str, object]]:
        started = time.perf_counter()
        if not _recall_allowed(self.store, actor, definition):
            RECALL_SECONDS.observe(time.perf_counter() - started)
            RECALLED_FACTS.observe(0)
            return []
        spec = _spec(definition)
        scopes = _read_scopes(spec)
        limit = top_k if top_k is not None else _top_k(spec)
        candidates = [
            row
            for row in self._recall_pool(actor, agent_id)
            if row.get("status") == "active" and row.get("scope") in scopes
        ]
        chosen = _rank(query, candidates, limit=limit)
        now = utcnow()
        for row in chosen:
            row["recall_count"] = _count(row.get("recall_count")) + 1
            row["last_recalled_at"] = now
        RECALL_SECONDS.observe(time.perf_counter() - started)
        RECALLED_FACTS.observe(len(chosen))
        return chosen

    def prompt_block(
        self,
        actor: Actor,
        *,
        query: str,
        agent_id: uuid.UUID | None,
        definition: dict[str, object],
    ) -> tuple[str, list[dict[str, object]]]:
        facts = self.recall(actor, query=query, agent_id=agent_id, definition=definition)
        return memory_block(facts), facts

    def save_from_tool(
        self, actor: Actor, arguments: dict[str, object], *, run: dict[str, object] | None
    ) -> dict[str, object]:
        if run is not None and (run.get("parent_run_id") or _count(run.get("depth")) > 0):
            raise ForbiddenError("memory.save is denied in a child run")
        definition = _run_definition(self.store, run)
        mode = _write_mode(self.store, actor, definition)
        if mode == "off":
            raise ForbiddenError("memory writes are off")
        scope = str(arguments.get("scope") or "user")
        if scope not in {"user", "agent_user", "agent"}:
            raise ValidationFailedError("scope is not writable from a run")
        content = _content(arguments.get("content"))
        explicit = True
        self._guard(content, explicit=explicit)
        category = _category(arguments.get("category"))
        trust = "high"
        source = "explicit"
        status = "active"
        if _untrusted_since_user(self.store, run):
            trust = "low"
            source = "tool_output"
            if category == "instruction":
                category = "fact"
        if scope == "agent" or (category == "instruction" and source != "explicit"):
            status = "pending_review"
        if scope == "agent":
            status = "pending_review"
        agent_id = _uuid(arguments.get("agent_id")) or _uuid(
            None if run is None else run.get("agent_id")
        )
        if scope in {"agent", "agent_user"} and agent_id is None:
            raise ValidationFailedError("agent_id is required")
        if mode == "explicit_only" and source == "tool_output":
            raise ForbiddenError("this agent only stores memories you ask for")
        row = self._insert(
            actor,
            scope=scope,
            user_id=None if scope == "agent" else actor.user_id,
            agent_id=agent_id if scope != "user" else None,
            team_id=None,
            content=content,
            category=category,
            source_kind=source,
            trust_level=trust,
            confidence=1.0,
            status=status,
            source_ref=_source_ref(run),
        )
        self._audit(actor, "memory.created", row["id"], {"scope": scope, "trust": trust})
        if status == "pending_review":
            self._propose(actor, row)
        return public_fact(self.store, row)

    def forget_from_tool(self, actor: Actor, arguments: dict[str, object]) -> int:
        fact_id = _uuid(arguments.get("fact_id"))
        if fact_id is not None:
            self.delete_user(actor, fact_id)
            return 1
        query = str(arguments.get("query") or "").strip()
        if not query:
            raise ValidationFailedError("fact_id or query is required")
        doomed = [
            row
            for row in self._owned(actor)
            if query.lower() in str(row.get("content") or "").lower()
        ]
        for row in doomed:
            self._rows().pop(_uuid_key(row["id"]), None)
            self._audit(actor, "memory.deleted", row["id"], {"scope": row["scope"]})
        self._gauges()
        return len(doomed)

    def search_from_tool(
        self, actor: Actor, arguments: dict[str, object], *, run: dict[str, object] | None
    ) -> list[dict[str, object]]:
        definition = _run_definition(self.store, run)
        scopes = arguments.get("scopes")
        allowed = _read_scopes(_spec(definition))
        if isinstance(scopes, list) and scopes:
            allowed = allowed & {str(item) for item in scopes}
        agent_id = _uuid(None if run is None else run.get("agent_id"))
        top = arguments.get("top_k")
        limit = top if isinstance(top, int) and not isinstance(top, bool) else None
        facts = self.recall(
            actor,
            query=str(arguments.get("query") or ""),
            agent_id=agent_id,
            definition={
                **definition,
                "memory": {**_spec(definition), "read_scopes": list(allowed)},
            },
            top_k=limit,
        )
        return [public_fact(self.store, row) for row in facts]

    def extract_turn(
        self,
        run: dict[str, object],
        user_text: str,
        assistant_text: str,
        *,
        model_output: str = "",
        tool_text: str = "",
    ) -> list[dict[str, object]]:
        """Apply extraction. Text that only appears in tool output is dropped."""
        if not self._extraction_on(run):
            return []
        seen = self.store.memory_extracted
        run_id = run.get("id")
        if run_id in seen:
            return []
        seen.add(run_id)
        visible = extraction_input(user_text, assistant_text).lower()
        ops = parse_ops(model_output) or heuristic_ops(user_text)
        ops = [op for op in ops if not _copied_from_tool(op, tool_text, visible)]
        actor = Actor(
            tenant_id=_as_uuid(run.get("tenant_id")),
            user_id=_as_uuid(run.get("user_id")),
            permissions=frozenset(),
        )
        return self.apply_ops(actor, run, ops)

    def apply_ops(
        self, actor: Actor, run: dict[str, object], ops: list[dict[str, object]]
    ) -> list[dict[str, object]]:
        saved: list[dict[str, object]] = []
        ids: list[str] = []
        for op in ops[:5]:
            result = self._one_op(actor, run, op)
            name = str(op.get("op") or "noop")
            EXTRACTION_OPS.labels(op=name, result=result).inc()
            if result == "applied":
                fact_id = str(op.get("_fact_id") or "")
                if fact_id:
                    ids.append(fact_id)
                    row = self._rows().get(uuid.UUID(fact_id))
                    if isinstance(row, dict):
                        saved.append(public_fact(self.store, row))
        if ids:
            self._audit(actor, "memory.extracted", actor.user_id, {"fact_ids": ids})
        return saved

    def _one_op(self, actor: Actor, run: dict[str, object], op: dict[str, object]) -> str:
        name = str(op.get("op") or "noop")
        gate = _gate_op(name, op)
        if gate:
            return gate
        if name == "delete":
            return self._op_delete(actor, op)
        content = str(op.get("content") or "").strip()
        confidence = _real(op.get("confidence"))
        category = category_of(op.get("category")) or "fact"
        status = "pending_review" if category == "instruction" else "active"
        scope = str(op.get("scope") or "user")
        if scope not in {"user", "agent_user"}:
            scope = "user"
        agent_id = _uuid(run.get("agent_id")) if scope == "agent_user" else None
        target = self._duplicate(actor, content, scope, agent_id)
        if name == "add" and target is not None:
            name = "update"
            op["target_fact_id"] = target["id"]
        if name == "update":
            return self._op_update(
                actor,
                run,
                op,
                content=content,
                category=category,
                status=status,
                scope=scope,
                agent_id=agent_id,
            )
        row = self._insert(
            actor,
            scope=scope,
            user_id=actor.user_id,
            agent_id=agent_id,
            team_id=None,
            content=content,
            category=category,
            source_kind="extracted",
            trust_level="high",
            confidence=confidence or 1.0,
            status=status,
            source_ref=_source_ref(run),
        )
        op["_fact_id"] = str(row["id"])
        return "applied"

    def _op_update(
        self,
        actor: Actor,
        run: dict[str, object],
        op: dict[str, object],
        *,
        content: str,
        category: str,
        status: str,
        scope: str,
        agent_id: uuid.UUID | None,
    ) -> str:
        target = self._find_owned(actor, _uuid(op.get("target_fact_id")))
        row = self._insert(
            actor,
            scope=scope,
            user_id=actor.user_id,
            agent_id=agent_id,
            team_id=None,
            content=content,
            category=category,
            source_kind="extracted",
            trust_level="high",
            confidence=_real(op.get("confidence"), 1),
            status=status,
            source_ref=_source_ref(run),
        )
        if target is not None:
            target["status"] = "superseded"
            target["superseded_by_id"] = row["id"]
            target["updated_at"] = utcnow()
        op["_fact_id"] = str(row["id"])
        return "applied"

    def _op_delete(self, actor: Actor, op: dict[str, object]) -> str:
        target = self._find_owned(actor, _uuid(op.get("target_fact_id")))
        if target is None:
            return "skipped"
        self._rows().pop(_uuid_key(target["id"]), None)
        op["_fact_id"] = str(target["id"])
        self._gauges()
        return "applied"

    def _duplicate(
        self, actor: Actor, content: str, scope: str, agent_id: uuid.UUID | None
    ) -> dict[str, object] | None:
        key = normalise(content)
        vector = _embed(content)
        best: dict[str, object] | None = None
        best_sim = 0.0
        for row in self._owned(actor):
            if row.get("status") != "active" or row.get("scope") != scope:
                continue
            if agent_id is not None and row.get("agent_id") != agent_id:
                continue
            if normalise(str(row.get("content") or "")) == key:
                return row
            sim = similarity(content, str(row.get("content") or ""), vector, row.get("embedding"))
            if sim >= dedupe_similarity() and sim > best_sim:
                best = row
                best_sim = sim
        return best

    def _insert(self, actor: Actor, **fields: object) -> dict[str, object]:
        content = str(fields["content"])
        now = utcnow()
        row: dict[str, object] = {
            "id": new_id(),
            "tenant_id": actor.tenant_id,
            "created_by": actor.user_id,
            "created_at": now,
            "updated_at": now,
            "embedding": _embed(content),
            "embedding_model_id": None,
            "superseded_by_id": None,
            "expires_at": None,
            "last_recalled_at": None,
            "recall_count": 0,
            **fields,
        }
        self._rows()[row["id"]] = row  # type: ignore[index]
        self._trim(row)
        self._gauges()
        return row

    def _trim(self, row: dict[str, object]) -> None:
        scope = str(row.get("scope"))
        if scope in {"user", "agent_user"}:
            pool = [
                item
                for item in self._rows().values()
                if item.get("tenant_id") == row.get("tenant_id")
                and item.get("user_id") == row.get("user_id")
                and item.get("status") == "active"
            ]
            limit = USER_FACT_LIMIT
        else:
            pool = [
                item
                for item in self._rows().values()
                if item.get("tenant_id") == row.get("tenant_id")
                and item.get("scope") == scope
                and item.get("status") == "active"
                and item.get("agent_id") == row.get("agent_id")
                and item.get("team_id") == row.get("team_id")
            ]
            limit = SHARED_FACT_LIMIT
        while len(pool) > limit:
            victim = min(pool, key=_trim_key)
            if victim.get("id") == row.get("id") and len(pool) == 1:
                break
            victim["status"] = "superseded"
            pool.remove(victim)

    def _rewrite(self, actor: Actor, row: dict[str, object], body: dict[str, object]) -> None:
        del actor
        if "content" in body and body.get("content") is not None:
            content = _content(body.get("content"))
            self._guard(content, explicit=True)
            row["content"] = content
            row["embedding"] = _embed(content)
        if body.get("category"):
            row["category"] = _category(body.get("category"))
        row["updated_at"] = utcnow()

    def _extraction_on(self, run: dict[str, object]) -> bool:
        if run.get("parent_run_id") or _count(run.get("depth")) > 0:
            return False
        if str(run.get("trigger") or "") not in _TRIGGERS:
            return False
        tenant = _as_uuid(run.get("tenant_id"))
        user = _as_uuid(run.get("user_id"))
        memory = _tenant_memory(self.store, tenant)
        if memory.get("enabled") is False or memory.get("extraction") is False:
            return False
        if not _user_enabled(self.store, user):
            return False
        definition = _run_definition(self.store, run)
        spec = _spec(definition)
        if spec.get("enabled") is False:
            return False
        return _writes(spec) == "auto"

    def _owned(self, actor: Actor) -> list[dict[str, object]]:
        return [
            row
            for row in self._rows().values()
            if row.get("tenant_id") == actor.tenant_id
            and row.get("user_id") == actor.user_id
            and row.get("scope") in {"user", "agent_user"}
        ]

    def _owned_row(self, actor: Actor, fact_id: uuid.UUID) -> dict[str, object]:
        row = self._rows().get(fact_id)
        if (
            not isinstance(row, dict)
            or row.get("tenant_id") != actor.tenant_id
            or row.get("user_id") != actor.user_id
            or row.get("scope") not in {"user", "agent_user"}
        ):
            raise NotFoundError("memory fact not found")
        return row

    def _find_owned(self, actor: Actor, fact_id: uuid.UUID | None) -> dict[str, object] | None:
        if fact_id is None:
            return None
        try:
            return self._owned_row(actor, fact_id)
        except NotFoundError:
            return None

    def _agent(self, actor: Actor, agent_id: uuid.UUID) -> dict[str, object]:
        agent = self.store.agents.get(agent_id)
        if not isinstance(agent, dict) or agent.get("tenant_id") != actor.tenant_id:
            raise NotFoundError("agent not found")
        return agent

    def _agent_row(
        self, actor: Actor, agent_id: uuid.UUID, fact_id: uuid.UUID
    ) -> dict[str, object]:
        agent = self._agent(actor, agent_id)
        if not _can_review(actor, agent):
            raise ForbiddenError("memory:manage_agent is required")
        row = self._rows().get(fact_id)
        if (
            not isinstance(row, dict)
            or row.get("tenant_id") != actor.tenant_id
            or row.get("agent_id") != agent_id
            or row.get("scope") != "agent"
        ):
            raise NotFoundError("memory fact not found")
        return row

    def _require_team(self, actor: Actor, team_id: uuid.UUID, *, write: bool) -> None:
        role = _team_role(self.store, actor, team_id)
        if role is None:
            raise NotFoundError("team not found")
        if write and role != "lead" and not actor.has("memory:manage_agent"):
            raise ForbiddenError("a team lead is required")

    def _recall_pool(self, actor: Actor, agent_id: uuid.UUID | None) -> list[dict[str, object]]:
        teams = _team_ids(self.store, actor)
        return [
            row
            for row in self._rows().values()
            if row.get("tenant_id") == actor.tenant_id and _in_recall(row, actor, agent_id, teams)
        ]

    def _propose(self, actor: Actor, row: dict[str, object]) -> None:
        self.store.domain_events.append(
            {
                "topic": "memory.fact_proposed",
                "fact_id": str(row["id"]),
                "scope": row["scope"],
                "agent_id": None if row.get("agent_id") is None else str(row.get("agent_id")),
            }
        )
        self.store.notifications.append(
            {
                "kind": "memory_review_requested",
                "tenant_id": str(actor.tenant_id),
                "fact_id": str(row["id"]),
            }
        )

    def _audit(self, actor: Actor, action: str, target: object, detail: dict[str, object]) -> None:
        remember(
            self.store,
            tenant_id=actor.tenant_id,
            actor_id=actor.user_id,
            action=action,
            target_type="memory_fact",
            target_id=target,
            detail=detail,
        )

    def _rows(self) -> dict[uuid.UUID, dict[str, object]]:
        return cast("dict[uuid.UUID, dict[str, object]]", self.store.memory_facts)

    def _guard(self, content: str, *, explicit: bool) -> None:
        reason = blocked_reason(content, explicit=explicit)
        if reason == "secret":
            raise ValidationFailedError("secrets are not stored in memory")
        if reason == "sensitive":
            raise ValidationFailedError("that needs an explicit request to remember")

    def _gauges(self) -> None:
        counts = {"user": 0, "agent": 0, "team": 0, "agent_user": 0}
        pending = 0
        for row in self._rows().values():
            if row.get("status") == "pending_review":
                pending += 1
            if row.get("status") == "active":
                scope = str(row.get("scope"))
                counts[scope] = counts.get(scope, 0) + 1
        for scope, count in counts.items():
            FACTS.labels(scope=scope).set(count)
        PENDING_REVIEW.set(pending)


def public_fact(store: Any, row: dict[str, object]) -> dict[str, object]:
    """CamelCase happens at the HTTP edge. This stays snake_case."""
    agent_id = row.get("agent_id")
    agent: dict[str, str] | None = None
    if isinstance(agent_id, uuid.UUID):
        found = store.agents.get(agent_id)
        name = str(found.get("name")) if isinstance(found, dict) else "Agent"
        agent = {"id": str(agent_id), "name": name}
    raw_source = row.get("source_ref")
    source = raw_source if isinstance(raw_source, dict) else {}
    conversation = source.get("conversation_id")
    message = source.get("message_id")
    origin = None
    if conversation or message:
        origin = {
            "conversation_id": None if not conversation else str(conversation),
            "message_id": None if not message else str(message),
        }
    return {
        "id": str(row["id"]),
        "scope": row["scope"],
        "agent": agent,
        "content": row["content"],
        "category": row["category"],
        "source_kind": row["source_kind"],
        "trust_level": row["trust_level"],
        "confidence": _real(row.get("confidence")),
        "status": row["status"],
        "created_at": _iso(row.get("created_at")),
        "last_recalled_at": _iso(row.get("last_recalled_at")) or None,
        "recall_count": _count(row.get("recall_count")),
        "source": origin,
    }


def _rank(query: str, rows: list[dict[str, object]], *, limit: int) -> list[dict[str, object]]:
    vector = _embed(query) if query else []
    now = utcnow()
    ranked: list[tuple[float, dict[str, object]]] = []
    standing: list[dict[str, object]] = []
    floor = min_similarity()
    for row in rows:
        created = row.get("created_at")
        when = created if isinstance(created, datetime) else now
        sim = similarity(query, str(row.get("content") or ""), vector, row.get("embedding"))
        if sim < floor:
            if _is_standing(row):
                standing.append(row)
            continue
        ranked.append(
            (
                score(
                    sim,
                    age_days=age_days(when, now),
                    recall_count=_count(row.get("recall_count")),
                ),
                row,
            )
        )
    ranked.sort(key=lambda item: item[0], reverse=True)
    chosen: list[dict[str, object]] = []
    tokens = 0
    for row in standing[:4]:
        tokens = _take(chosen, row, tokens, limit)
    for _value, row in ranked:
        if any(item.get("id") == row.get("id") for item in chosen):
            continue
        tokens = _take(chosen, row, tokens, limit)
    return chosen


def _take(chosen: list[dict[str, object]], row: dict[str, object], tokens: int, limit: int) -> int:
    if len(chosen) >= limit:
        return tokens
    cost = estimate_fact_tokens(str(row.get("content") or ""))
    if tokens + cost > TOKEN_BUDGET:
        return tokens
    chosen.append(row)
    return tokens + cost


def _gate_op(name: str, op: dict[str, object]) -> str:
    """A non-empty string means the operation is not applied."""
    if name == "noop":
        return "skipped"
    explicit = bool(op.get("explicit"))
    confidence = _real(op.get("confidence"))
    if not explicit and confidence < MIN_CONFIDENCE:
        return "low_confidence"
    if name == "delete":
        return ""
    content = str(op.get("content") or "").strip()
    if not content:
        return "empty"
    if blocked_reason(content, explicit=explicit):
        return "blocked"
    return ""


def _in_recall(
    row: dict[str, object],
    actor: Actor,
    agent_id: uuid.UUID | None,
    teams: set[uuid.UUID],
) -> bool:
    scope = row.get("scope")
    if scope == "user":
        return row.get("user_id") == actor.user_id
    if scope == "agent_user":
        return row.get("user_id") == actor.user_id and (
            agent_id is None or row.get("agent_id") == agent_id
        )
    if scope == "agent":
        return agent_id is not None and row.get("agent_id") == agent_id
    return scope == "team" and row.get("team_id") in teams


def _uuid_key(value: object) -> uuid.UUID:
    if isinstance(value, uuid.UUID):
        return value
    raise NotFoundError("memory fact not found")


def _count(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return value


def _real(value: object, default: float = 0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    return float(value)


def _copied_from_tool(op: dict[str, object], tool_text: str, visible: str) -> bool:
    """A fact copied from a tool or document, and absent from the turn, is not stored."""
    content = " ".join(str(op.get("content") or "").split()).lower()
    source = " ".join(tool_text.split()).lower()
    if not content or not source:
        return False
    return content in source and content not in visible


def _is_standing(row: dict[str, object]) -> bool:
    return (
        row.get("category") in _STANDING
        and row.get("trust_level") != "low"
        and row.get("scope") in {"user", "agent_user"}
        and row.get("status") == "active"
    )


def _embed(text: str) -> list[float]:
    if not text:
        return embed_texts([" "], model="fake-embed", dimensions=dimensions())[0]
    return embed_texts([text], model="fake-embed", dimensions=dimensions())[0]


def _content(value: object) -> str:
    text = " ".join(str(value or "").split())
    if not text:
        raise ValidationFailedError("content is required")
    if len(text) > CONTENT_LIMIT:
        raise ValidationFailedError("content is longer than 500 characters")
    return text


def _category(value: object) -> str:
    found = category_of(value)
    if not found:
        raise ValidationFailedError("unknown memory category")
    return found


def _uuid(value: object) -> uuid.UUID | None:
    if isinstance(value, uuid.UUID):
        return value
    if isinstance(value, str) and value:
        try:
            return uuid.UUID(value)
        except ValueError:
            return None
    return None


def _as_uuid(value: object) -> uuid.UUID:
    found = _uuid(value)
    if found is None:
        raise NotFoundError("memory fact not found")
    return found


def _iso(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return ""


def _status_ok(row: dict[str, object], status: str) -> bool:
    if not status:
        return True
    return row.get("status") == status


def _scope_ok(row: dict[str, object], scope: str | None) -> bool:
    return scope is None or row.get("scope") == scope


def _agent_ok(row: dict[str, object], agent_id: uuid.UUID | None) -> bool:
    return agent_id is None or row.get("agent_id") == agent_id


def _category_ok(row: dict[str, object], category: str | None) -> bool:
    return category is None or row.get("category") == category


def _search(rows: list[dict[str, object]], query: str) -> list[dict[str, object]]:
    text = query.strip()
    if not text:
        return rows
    if len(text.split()) >= 3:
        vector = _embed(text)
        scored = [
            (
                similarity(text, str(row.get("content") or ""), vector, row.get("embedding")),
                row,
            )
            for row in rows
        ]
        scored = [item for item in scored if item[0] > 0]
        scored.sort(key=lambda item: item[0], reverse=True)
        return [row for _score, row in scored]
    needle = text.lower()
    return [row for row in rows if needle in str(row.get("content") or "").lower()]


def _spec(definition: dict[str, object]) -> dict[str, object]:
    raw = definition.get("memory")
    return raw if isinstance(raw, dict) else {}


def _writes(spec: dict[str, object]) -> str:
    return str(spec.get("user_writes") or spec.get("userWrites") or "auto")


def _read_scopes(spec: dict[str, object]) -> set[str]:
    raw = spec.get("read_scopes") if "read_scopes" in spec else spec.get("readScopes")
    if not isinstance(raw, list) or not raw:
        return {"user", "agent"}
    return {str(item) for item in raw}


def _top_k(spec: dict[str, object]) -> int:
    raw = spec.get("recall_top_k", spec.get("recallTopK", DEFAULT_TOP_K))
    if isinstance(raw, int) and not isinstance(raw, bool) and raw > 0:
        return raw
    return DEFAULT_TOP_K


def _tenant_memory(store: Any, tenant_id: uuid.UUID) -> dict[str, object]:
    settings = getattr(store, "tenant_settings", {})
    current = settings.get(tenant_id) if isinstance(settings, dict) else {}
    if not isinstance(current, dict):
        return {}
    memory = current.get("memory")
    return memory if isinstance(memory, dict) else {}


def _user_enabled(store: Any, user_id: uuid.UUID) -> bool:
    settings = getattr(store, "user_settings", {})
    current = settings.get(user_id) if isinstance(settings, dict) else {}
    if not isinstance(current, dict):
        return True
    return bool(current.get("memory_enabled", True))


def _recall_allowed(store: Any, actor: Actor, definition: dict[str, object]) -> bool:
    memory = _tenant_memory(store, actor.tenant_id)
    if memory.get("enabled") is False:
        return False
    if not _user_enabled(store, actor.user_id):
        return False
    spec = _spec(definition)
    return spec.get("enabled") is not False


def _write_mode(store: Any, actor: Actor, definition: dict[str, object]) -> str:
    if not _recall_allowed(store, actor, definition):
        return "off"
    writes = _writes(_spec(definition))
    if writes == "off":
        return "off"
    if writes == "explicit_only":
        return "explicit_only"
    return "auto"


def _run_definition(store: Any, run: dict[str, object] | None) -> dict[str, object]:
    if run is None:
        return {}
    version_id = run.get("agent_version_id")
    if not isinstance(version_id, uuid.UUID):
        agent_id = run.get("agent_id")
        agent = store.agents.get(agent_id) if isinstance(agent_id, uuid.UUID) else None
        if isinstance(agent, dict):
            version_id = agent.get("published_version_id")
    version = store.versions.get(version_id) if isinstance(version_id, uuid.UUID) else None
    definition = version.get("definition") if isinstance(version, dict) else None
    if isinstance(definition, dict):
        return {str(key): value for key, value in definition.items()}
    return {}


def _source_ref(run: dict[str, object] | None) -> dict[str, object]:
    if run is None:
        return {}
    return {
        "conversation_id": run.get("conversation_id"),
        "message_id": run.get("input_message_id"),
        "run_id": run.get("id"),
    }


def _untrusted_since_user(store: Any, run: dict[str, object] | None) -> bool:
    if run is None:
        return False
    if run.get("untrusted_since_user"):
        return True
    run_id = run.get("id")
    calls = getattr(store, "tool_calls", {})
    if not isinstance(calls, dict):
        return False
    for call in calls.values():
        if not isinstance(call, dict) or call.get("run_id") != run_id:
            continue
        name = str(call.get("qualified_name") or "")
        if name.startswith("memory."):
            continue
        if call.get("status") == "succeeded":
            return True
    return False


def _can_review(actor: Actor, agent: dict[str, object]) -> bool:
    return actor.has("memory:manage_agent") or can_edit(agent, actor)


def _team_role(store: Any, actor: Actor, team_id: uuid.UUID) -> str | None:
    roster = getattr(store, "team_roster", {})
    team = roster.get(team_id) if isinstance(roster, dict) else None
    if not isinstance(team, dict) or team.get("tenant_id") != actor.tenant_id:
        if str(team_id) in actor.team_ids:
            return "member"
        return None
    members = team.get("members")
    if not isinstance(members, dict):
        return None
    role = members.get(str(actor.user_id))
    if isinstance(role, str):
        return role
    if str(team_id) in actor.team_ids:
        return "member"
    return None


def _team_ids(store: Any, actor: Actor) -> set[uuid.UUID]:
    found = {uuid.UUID(item) for item in actor.team_ids if _uuid(item)}
    roster = getattr(store, "team_roster", {})
    if not isinstance(roster, dict):
        return found
    for team_id, team in roster.items():
        if not isinstance(team_id, uuid.UUID) or not isinstance(team, dict):
            continue
        if team.get("tenant_id") != actor.tenant_id:
            continue
        members = team.get("members")
        if isinstance(members, dict) and str(actor.user_id) in members:
            found.add(team_id)
    return found


def _trim_key(row: dict[str, object]) -> tuple[int, str]:
    created = row.get("created_at")
    stamp = created.isoformat() if isinstance(created, datetime) else ""
    return (_count(row.get("recall_count")), stamp)

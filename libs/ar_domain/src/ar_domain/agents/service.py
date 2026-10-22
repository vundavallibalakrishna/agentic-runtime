"""Agent lifecycle on the process store. Spec: docs/03-specs/05-agent-registry.md.

The HTTP process keeps product state in memory (OQ-31). This service is the
registry those routes call. Audit actions and domain events are appended on
the same store.
"""

import hashlib
import re
import uuid
from typing import Any, cast

import orjson
from pydantic import JsonValue

from ar_common.errors import (
    ArError,
    ConflictError,
    ErrorCode,
    FieldError,
    NotFoundError,
    ValidationFailedError,
)
from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_domain.agents.access import Actor, can_archive, can_edit, can_publish, can_see
from ar_domain.agents.logic import definition_hash
from ar_domain.agents.templates import (
    TEMPLATES,
    builder_definition,
    helpdesk_definition,
    template_definition,
)
from ar_domain.agents.validation import reference_issues, schema_errors, split_issues
from ar_domain.references import ReferenceIssue, ResolveContext

_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}$")
_MAX_AGENTS = 200
_MAX_BYTES = 256 * 1024


def _too_large(raw: dict[str, object]) -> bool:
    try:
        return len(orjson.dumps(cast("JsonValue", raw))) > _MAX_BYTES
    except TypeError:
        return len(str(raw).encode()) > _MAX_BYTES


_BUILTIN = frozenset({"assistant", "builder"})
_ACTIVE = frozenset({"queued", "running", "waiting_approval", "waiting_input"})


def _issue(item: ReferenceIssue) -> FieldError:
    return FieldError(loc=list(item.loc), msg=item.msg, type=item.type)


def _public_issues(items: list[ReferenceIssue]) -> list[dict[str, object]]:
    return [{"loc": list(item.loc), "msg": item.msg, "type": item.type} for item in items]


def etag_for(row: dict[str, object]) -> str:
    """Hex sha256 of id and the row clock. Spec: api-conventions §7."""
    stamp = row.get("updated_at") or row.get("created_at")
    text = stamp.isoformat() if hasattr(stamp, "isoformat") else str(stamp)
    return hashlib.sha256(f"{row.get('id')}|{text}".encode()).hexdigest()


def require_match(row: dict[str, object], if_match: str | None) -> None:
    """Reject a stale writer. A missing header stays unconditional (OQ-34)."""
    if if_match is None or if_match == "":
        return
    expected = etag_for(row)
    if if_match.strip('"') != expected:
        raise ArError(ErrorCode.PRECONDITION_FAILED, "etag mismatch")


class AgentLifecycle:
    """Lifecycle operations over the chat store dictionaries."""

    def __init__(self, store: Any) -> None:
        self.store = store

    def aliases(self, tenant_id: uuid.UUID) -> set[str]:
        names: set[str] = set()
        for row in self.store.aliases.values():
            owner = row.get("tenant_id")
            if owner is None or owner == tenant_id:
                names.add(str(row.get("alias")))
        return names

    def context(self, actor: Actor, *, warnings: bool = False) -> ResolveContext:
        return ResolveContext(
            tenant_id=str(actor.tenant_id),
            alias_names=self.aliases(actor.tenant_id),
            tool_servers=self._approved_servers(actor.tenant_id),
            sandbox_templates=self._sandbox_templates(actor.tenant_id),
            knowledge_collections=self._knowledge_collections(actor.tenant_id),
            treat_unknown_as_warning=warnings,
        )

    def _knowledge_collections(self, tenant_id: uuid.UUID) -> set[str]:
        names: set[str] = set()
        rows = getattr(self.store, "knowledge_collections", {})
        for row in rows.values():
            if row.get("tenant_id") == tenant_id:
                names.add(str(row.get("slug")))
        return names

    def _sandbox_templates(self, tenant_id: uuid.UUID) -> set[str]:
        names: set[str] = set()
        templates = getattr(self.store, "sandbox_templates", {})
        for row in templates.values():
            owner = row.get("tenant_id")
            if owner is not None and owner != tenant_id:
                continue
            if row.get("status") == "active":
                names.add(str(row.get("slug")))
        return names

    def _approved_servers(self, tenant_id: uuid.UUID) -> set[str]:
        names: set[str] = set()
        servers = getattr(self.store, "tool_servers", {})
        for row in servers.values():
            owner = row.get("tenant_id")
            if owner is not None and owner != tenant_id:
                continue
            if row.get("status") == "approved" and row.get("disabled_at") is None:
                names.add(str(row.get("slug")))
        return names

    def ensure_builtins(self, tenant_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Published assistant, Helpdesk and the built-in builder."""
        self.store.ensure_assistant(tenant_id, user_id)
        self._ensure(
            "helpdesk",
            "Helpdesk",
            "Answers common requests.",
            helpdesk_definition(),
            tenant_id=tenant_id,
            user_id=user_id,
            builtin=False,
        )
        self._ensure(
            "builder",
            "Builder",
            "Drafts an agent from a sentence. It does not publish.",
            builder_definition(),
            tenant_id=tenant_id,
            user_id=user_id,
            builtin=True,
        )

    def _ensure(
        self,
        slug: str,
        name: str,
        description: str,
        definition: dict[str, object],
        *,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        builtin: bool,
    ) -> None:
        for agent in self.store.agents.values():
            if agent["tenant_id"] == tenant_id and agent["slug"] == slug:
                agent["builtin"] = builtin or bool(agent.get("builtin"))
                return
        self._insert(
            tenant_id,
            user_id,
            slug=slug,
            name=name,
            description=description,
            visibility="tenant",
            definition=definition,
            published=True,
            builtin=builtin,
        )

    def _insert(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        *,
        slug: str,
        name: str,
        description: str,
        visibility: str,
        definition: dict[str, object],
        published: bool,
        builtin: bool = False,
        risk_tier: str = "low",
    ) -> dict[str, object]:
        now = utcnow()
        agent_id = new_id()
        version_id = new_id()
        stored = dict(definition)
        stored.pop("resolved", None)
        self.store.versions[version_id] = {
            "id": version_id,
            "tenant_id": tenant_id,
            "agent_id": agent_id,
            "version": 1,
            "state": "published" if published else "draft",
            "definition": stored,
            "definition_hash": definition_hash(stored),
            "change_note": "seed" if published else "",
            "created_by": user_id,
            "created_at": now,
            "updated_at": now,
            "published_at": now if published else None,
            "published_by": user_id if published else None,
        }
        agent = {
            "id": agent_id,
            "tenant_id": tenant_id,
            "slug": slug,
            "name": name,
            "description": description,
            "owner_user_id": user_id,
            "owner_team_id": None,
            "visibility": visibility,
            "status": "published" if published else "draft",
            "disabled": False,
            "disabled_at": None,
            "disabled_reason": None,
            "risk_tier": risk_tier,
            "draft_version_id": None if published else version_id,
            "published_version_id": version_id if published else None,
            "builtin": builtin,
            "dirty": False,
            "created_at": now,
            "updated_at": now,
        }
        self.store.agents[agent_id] = agent
        if published:
            self._bind(tenant_id, version_id, stored)
        return agent

    def _bind(
        self, tenant_id: uuid.UUID, version_id: uuid.UUID, definition: dict[str, object]
    ) -> None:
        model = definition.get("model")
        alias = model.get("alias") if isinstance(model, dict) else None
        if not isinstance(alias, str):
            return
        alias_id = None
        for row in self.store.aliases.values():
            if str(row.get("alias")) == alias:
                alias_id = row.get("id")
                break
        target = alias_id if isinstance(alias_id, uuid.UUID) else uuid.UUID(int=0)
        self.store.bindings[(version_id, "model_alias", str(target), alias)] = {
            "tenant_id": tenant_id,
            "agent_version_id": version_id,
            "kind": "model_alias",
            "target_id": target,
            "target_key": alias,
        }
        tools = definition.get("tools")
        if not isinstance(tools, list):
            return
        for binding in tools:
            if not isinstance(binding, dict):
                continue
            server = binding.get("server")
            if not isinstance(server, str) or not server:
                continue
            self.store.bindings[(version_id, "tool_server", server, server)] = {
                "tenant_id": tenant_id,
                "agent_version_id": version_id,
                "kind": "tool_server",
                "target_id": server,
                "target_key": server,
            }

    def _agent(self, actor: Actor, agent_id: uuid.UUID) -> dict[str, object]:
        agent = self.store.agents.get(agent_id)
        if not isinstance(agent, dict) or agent.get("tenant_id") != actor.tenant_id:
            raise NotFoundError()
        if not can_see(agent, actor):
            raise NotFoundError()
        return agent

    def _version(self, agent: dict[str, object], ref: str) -> dict[str, object]:
        if ref == "draft":
            version_id = agent.get("draft_version_id")
        elif ref == "published":
            version_id = agent.get("published_version_id")
        else:
            number = int(ref)
            version_id = next(
                (
                    row["id"]
                    for row in self.store.versions.values()
                    if row.get("agent_id") == agent["id"] and row.get("version") == number
                ),
                None,
            )
        if not isinstance(version_id, uuid.UUID):
            raise NotFoundError()
        row = self.store.versions.get(version_id)
        if not isinstance(row, dict):
            raise NotFoundError()
        return row

    def summary(self, agent: dict[str, object], actor: Actor) -> dict[str, object]:
        body = self.store._agent_out(agent)
        published = agent.get("published_version_id")
        draft = agent.get("draft_version_id")
        published_row = (
            self.store.versions.get(published) if isinstance(published, uuid.UUID) else None
        )
        draft_row = self.store.versions.get(draft) if isinstance(draft, uuid.UUID) else None
        body.update(
            {
                "description": agent.get("description") or "",
                "visibility": agent.get("visibility"),
                "status": agent.get("status"),
                "disabled": bool(agent.get("disabled")),
                "risk_tier": agent.get("risk_tier"),
                "owner": {
                    "id": (
                        None if agent.get("owner_user_id") is None else str(agent["owner_user_id"])
                    ),
                    "display_name": (
                        actor.display_name
                        if str(agent.get("owner_user_id")) == str(actor.user_id)
                        else "Owner"
                    ),
                },
                "owner_team": None,
                "published_version": (
                    None if not isinstance(published_row, dict) else published_row.get("version")
                ),
                "draft_version": (
                    None if not isinstance(draft_row, dict) else draft_row.get("version")
                ),
                "can_edit": can_edit(agent, actor),
                "favourite": agent["id"]
                in self.store.favourites.get((actor.tenant_id, actor.user_id), set()),
                "etag": etag_for(agent),
                "builtin": bool(agent.get("builtin")),
            }
        )
        return cast("dict[str, object]", body)

    def detail(self, agent: dict[str, object], actor: Actor) -> dict[str, object]:
        body = self.summary(agent, actor)
        editor = can_edit(agent, actor)
        published_id = agent.get("published_version_id")
        draft_id = agent.get("draft_version_id")
        if isinstance(published_id, uuid.UUID):
            body["published"] = self._version_out(self.store.versions[published_id], editor=True)
        else:
            body["published"] = None
        if editor and isinstance(draft_id, uuid.UUID):
            body["draft"] = self._version_out(self.store.versions[draft_id], editor=True)
        else:
            body["draft"] = None
        return body

    def _version_out(self, row: dict[str, object], *, editor: bool) -> dict[str, object]:
        body = self.store._public(row)
        body["etag"] = etag_for(row)
        if not editor:
            definition = row.get("definition")
            redacted: dict[str, object] = {}
            if isinstance(definition, dict):
                for key in ("persona", "starter_prompts", "channels"):
                    if key in definition:
                        redacted[key] = definition[key]
            body["definition"] = redacted
        return cast("dict[str, object]", body)

    def list_agents(
        self,
        actor: Actor,
        *,
        q: str | None = None,
        status: str | None = None,
        visibility: str | None = None,
        owner: str | None = None,
    ) -> list[dict[str, object]]:
        self.ensure_builtins(actor.tenant_id, actor.user_id)
        found: list[dict[str, object]] = []
        for agent in self.store.agents.values():
            if not can_see(agent, actor):
                continue
            if status is not None and agent.get("status") != status:
                continue
            if visibility is not None and agent.get("visibility") != visibility:
                continue
            if owner == "me" and str(agent.get("owner_user_id")) != str(actor.user_id):
                continue
            if q:
                name = str(agent.get("name", ""))
                slug = str(agent.get("slug", ""))
                description = str(agent.get("description", ""))
                haystack = f"{name} {slug} {description}"
                if q.lower() not in haystack.lower():
                    continue
            found.append(self.summary(agent, actor))
        found.sort(key=lambda item: str(item.get("name", "")).lower())
        return found

    def create(
        self,
        actor: Actor,
        *,
        slug: str,
        name: str,
        description: str = "",
        visibility: str = "private",
        risk_tier: str = "low",
        template: str | None = None,
        definition: dict[str, object] | None = None,
    ) -> dict[str, object]:
        if not actor.has("agents:create") and not actor.has("agents:manage_all"):
            raise ArError(ErrorCode.FORBIDDEN, "missing permission agents:create")
        if not _SLUG.match(slug):
            raise ValidationFailedError("slug is invalid")
        if (
            visibility == "tenant"
            and not actor.has("agents:publish")
            and not actor.has("agents:manage_all")
        ):
            raise ArError(ErrorCode.FORBIDDEN, "tenant visibility requires agents:publish")
        count = sum(
            1 for row in self.store.agents.values() if row.get("tenant_id") == actor.tenant_id
        )
        if count >= _MAX_AGENTS:
            raise ArError(ErrorCode.PLAN_LIMIT_REACHED, "max_agents")
        if any(
            row.get("tenant_id") == actor.tenant_id and row.get("slug") == slug
            for row in self.store.agents.values()
        ):
            raise ConflictError("slug already exists")
        chosen = template if template in TEMPLATES else "blank"
        raw = definition if definition is not None else template_definition(chosen, name=name)
        if _too_large(raw):
            raise ArError(ErrorCode.PAYLOAD_TOO_LARGE, "definition is larger than 256 KiB")
        normalised, issues = schema_errors(raw)
        if normalised is None:
            raise ValidationFailedError(
                "definition is invalid", errors=[_issue(item) for item in issues]
            )
        agent = self._insert(
            actor.tenant_id,
            actor.user_id,
            slug=slug,
            name=name,
            description=description,
            visibility=visibility,
            definition=normalised,
            published=False,
            risk_tier=risk_tier,
        )
        self._audit(actor, "agent.created", agent["id"], {"slug": slug})
        return self.detail(agent, actor)

    def update(
        self,
        actor: Actor,
        agent_id: uuid.UUID,
        *,
        if_match: str | None,
        fields: dict[str, object],
    ) -> dict[str, object]:
        agent = self._agent(actor, agent_id)
        if not can_edit(agent, actor):
            raise ArError(ErrorCode.FORBIDDEN, "you cannot edit this agent")
        require_match(agent, if_match)
        if (
            fields.get("visibility") == "tenant"
            and not actor.has("agents:publish")
            and not actor.has("agents:manage_all")
        ):
            raise ArError(ErrorCode.FORBIDDEN, "tenant visibility requires agents:publish")
        for key in (
            "name",
            "description",
            "visibility",
            "risk_tier",
            "owner_team_id",
            "owner_user_id",
        ):
            if key in fields and fields[key] is not None:
                agent[key] = fields[key]
        agent["updated_at"] = utcnow()
        self._audit(actor, "agent.updated", agent_id, {"fields": sorted(fields)})
        return self.detail(agent, actor)

    def delete(self, actor: Actor, agent_id: uuid.UUID) -> None:
        agent = self._agent(actor, agent_id)
        if not can_archive(agent, actor):
            raise ArError(ErrorCode.FORBIDDEN, "you cannot delete this agent")
        if agent.get("builtin") or agent.get("slug") in _BUILTIN:
            raise ArError(ErrorCode.INVALID_STATE, "this agent cannot be deleted")
        if agent.get("published_version_id") is not None:
            raise ArError(
                ErrorCode.INVALID_STATE, "archive a published agent instead of deleting it"
            )
        used = any(
            row.get("agent_id") == agent_id and row.get("deleted_at") is None
            for row in self.store.conversations.values()
        )
        if used:
            raise ArError(ErrorCode.INVALID_STATE, "archive an agent that has conversations")
        del self.store.agents[agent_id]
        self._audit(actor, "agent.deleted", agent_id, {})

    def archive(self, actor: Actor, agent_id: uuid.UUID) -> dict[str, object]:
        agent = self._agent(actor, agent_id)
        if not can_archive(agent, actor):
            raise ArError(ErrorCode.FORBIDDEN, "you cannot archive this agent")
        if agent.get("slug") in _BUILTIN:
            raise ArError(ErrorCode.INVALID_STATE, "this agent cannot be archived")
        agent["status"] = "archived"
        agent["updated_at"] = utcnow()
        self._audit(actor, "agent.archived", agent_id, {})
        return self.detail(agent, actor)

    def unarchive(self, actor: Actor, agent_id: uuid.UUID) -> dict[str, object]:
        agent = self._agent(actor, agent_id)
        if not can_archive(agent, actor):
            raise ArError(ErrorCode.FORBIDDEN, "you cannot unarchive this agent")
        agent["status"] = "published" if agent.get("published_version_id") else "draft"
        agent["updated_at"] = utcnow()
        self._audit(actor, "agent.unarchived", agent_id, {})
        return self.detail(agent, actor)

    def save_draft(
        self,
        actor: Actor,
        agent_id: uuid.UUID,
        definition: dict[str, object],
        *,
        change_note: str = "",
        if_match: str | None = None,
    ) -> dict[str, object]:
        agent = self._agent(actor, agent_id)
        if not can_edit(agent, actor):
            raise ArError(ErrorCode.FORBIDDEN, "you cannot edit this agent")
        draft_id = agent.get("draft_version_id")
        if isinstance(draft_id, uuid.UUID):
            require_match(self.store.versions[draft_id], if_match)
        if _too_large(definition):
            raise ArError(ErrorCode.PAYLOAD_TOO_LARGE, "definition is larger than 256 KiB")
        normalised, issues = schema_errors(definition)
        if normalised is None:
            raise ValidationFailedError(
                "definition is invalid", errors=[_issue(item) for item in issues]
            )
        now = utcnow()
        if (
            isinstance(draft_id, uuid.UUID)
            and self.store.versions[draft_id].get("state") == "draft"
        ):
            row = self.store.versions[draft_id]
            row["definition"] = normalised
            row["definition_hash"] = definition_hash(normalised)
            row["change_note"] = change_note or row.get("change_note") or ""
            row["updated_at"] = now
        else:
            row = self._new_version(actor, agent, normalised, change_note)
        agent["draft_version_id"] = row["id"]
        agent["dirty"] = True
        agent["updated_at"] = now
        self._audit(
            actor, "agent.draft_saved", agent["id"], {"definition_hash": row["definition_hash"]}
        )
        return self._version_out(row, editor=True)

    def _new_version(
        self,
        actor: Actor,
        agent: dict[str, object],
        definition: dict[str, object],
        change_note: str,
    ) -> dict[str, object]:
        numbers = [
            int(row["version"])
            for row in self.store.versions.values()
            if row.get("agent_id") == agent["id"] and isinstance(row.get("version"), int)
        ]
        now = utcnow()
        version_id = new_id()
        row = {
            "id": version_id,
            "tenant_id": actor.tenant_id,
            "agent_id": agent["id"],
            "version": (max(numbers) if numbers else 0) + 1,
            "state": "draft",
            "definition": definition,
            "definition_hash": definition_hash(definition),
            "change_note": change_note,
            "created_by": actor.user_id,
            "created_at": now,
            "updated_at": now,
            "published_at": None,
            "published_by": None,
        }
        self.store.versions[version_id] = row
        return row

    def validate(
        self, actor: Actor, agent_id: uuid.UUID, *, version_ref: str = "draft"
    ) -> dict[str, object]:
        agent = self._agent(actor, agent_id)
        if not can_edit(agent, actor):
            raise ArError(ErrorCode.FORBIDDEN, "you cannot validate this agent")
        row = self._version(agent, version_ref if version_ref else "draft")
        definition = row.get("definition")
        if not isinstance(definition, dict):
            raise ValidationFailedError("definition is invalid")
        normalised, schema = schema_errors(definition)
        if normalised is None:
            return {
                "valid": False,
                "errors": _public_issues(schema),
                "warnings": [],
                "resolved": {},
            }
        issues, resolved = reference_issues(normalised, self.context(actor, warnings=True))
        errors, warnings = split_issues(issues)
        return {
            "valid": not errors,
            "errors": _public_issues(errors),
            "warnings": _public_issues(warnings),
            "resolved": resolved,
        }

    def publish(
        self,
        actor: Actor,
        agent_id: uuid.UUID,
        *,
        change_note: str = "",
        if_match: str | None = None,
    ) -> dict[str, object]:
        agent = self._agent(actor, agent_id)
        if not can_publish(agent, actor):
            raise ArError(ErrorCode.FORBIDDEN, "you cannot publish this agent")
        draft_id = agent.get("draft_version_id") or agent.get("published_version_id")
        if not isinstance(draft_id, uuid.UUID):
            raise ArError(ErrorCode.INVALID_STATE, "nothing to publish")
        require_match(self.store.versions[draft_id], if_match)
        version = self.store.versions[draft_id]
        definition = version.get("definition")
        if not isinstance(definition, dict):
            raise ValidationFailedError("definition is invalid")
        normalised, schema = schema_errors(definition)
        if normalised is None:
            raise ValidationFailedError(
                "definition is invalid", errors=[_issue(item) for item in schema]
            )
        issues, resolved = reference_issues(normalised, self.context(actor, warnings=False))
        errors, _warnings = split_issues(issues)
        if errors:
            raise ArError(
                ErrorCode.UNKNOWN_REFERENCE,
                errors[0].msg,
                errors=[_issue(item) for item in errors],
            )
        normalised = dict(normalised)
        normalised.pop("resolved", None)
        digest = definition_hash(normalised)
        normalised["resolved"] = resolved
        previous = agent.get("published_version_id")
        if isinstance(previous, uuid.UUID) and previous != draft_id:
            prior = self.store.versions.get(previous)
            if isinstance(prior, dict) and prior.get("state") == "published":
                prior["state"] = "superseded"
                prior["updated_at"] = utcnow()
        now = utcnow()
        version["definition"] = normalised
        version["definition_hash"] = digest
        version["state"] = "published"
        version["change_note"] = change_note or version.get("change_note") or ""
        version["published_at"] = now
        version["published_by"] = actor.user_id
        version["updated_at"] = now
        agent["published_version_id"] = draft_id
        agent["draft_version_id"] = None
        agent["status"] = "published"
        agent["dirty"] = False
        agent["updated_at"] = now
        self._bind(actor.tenant_id, draft_id, normalised)
        self._audit(
            actor,
            "agent.published",
            agent_id,
            {"definition_hash": digest, "version": version["version"]},
        )
        self._event(
            "agent.published",
            {
                "agent_id": str(agent_id),
                "agent_version_id": str(draft_id),
                "version": version["version"],
            },
        )
        return self.detail(agent, actor)

    def rollback(
        self, actor: Actor, agent_id: uuid.UUID, *, version: int, change_note: str
    ) -> dict[str, object]:
        agent = self._agent(actor, agent_id)
        if not can_publish(agent, actor):
            raise ArError(ErrorCode.FORBIDDEN, "you cannot roll back this agent")
        source = self._version(agent, str(version))
        definition = source.get("definition")
        if not isinstance(definition, dict):
            raise ValidationFailedError("definition is invalid")
        cleaned = dict(definition)
        cleaned.pop("resolved", None)
        normalised, schema = schema_errors(cleaned)
        if normalised is None:
            raise ValidationFailedError(
                "definition is invalid", errors=[_issue(item) for item in schema]
            )
        issues, _resolved = reference_issues(normalised, self.context(actor))
        errors, _warnings = split_issues(issues)
        if errors:
            raise ArError(
                ErrorCode.UNKNOWN_REFERENCE, errors[0].msg, errors=[_issue(item) for item in errors]
            )
        row = self._new_version(actor, agent, normalised, change_note)
        agent["draft_version_id"] = row["id"]
        agent["updated_at"] = utcnow()
        self.publish(actor, agent_id, change_note=change_note)
        self._audit(actor, "agent.rolled_back", agent_id, {"version": version})
        return self.detail(self.store.agents[agent_id], actor)

    def duplicate(
        self, actor: Actor, agent_id: uuid.UUID, *, slug: str, name: str
    ) -> dict[str, object]:
        agent = self._agent(actor, agent_id)
        source_id = agent.get("draft_version_id") or agent.get("published_version_id")
        definition: dict[str, object] = {}
        if isinstance(source_id, uuid.UUID):
            raw = self.store.versions[source_id].get("definition")
            if isinstance(raw, dict):
                definition = dict(raw)
                definition.pop("resolved", None)
        created = self.create(
            actor,
            slug=slug,
            name=name,
            description=str(agent.get("description") or ""),
            visibility="private",
            definition=definition or None,
        )
        self._audit(actor, "agent.duplicated", agent_id, {"slug": slug})
        return created

    def disable(
        self, actor: Actor, agent_id: uuid.UUID, *, reason: str, cancel_active: bool
    ) -> dict[str, object]:
        agent = self._agent(actor, agent_id)
        if not actor.has("agents:disable") and not actor.has("agents:manage_all"):
            raise ArError(ErrorCode.FORBIDDEN, "missing permission agents:disable")
        now = utcnow()
        agent["disabled"] = True
        agent["disabled_at"] = now
        agent["disabled_reason"] = reason
        agent["updated_at"] = now
        if cancel_active:
            self._cancel_runs(agent_id)
        self._audit(actor, "agent.disabled", agent_id, {"reason": reason})
        self._event("agent.disabled", {"agent_id": str(agent_id), "reason": reason})
        return self.detail(agent, actor)

    def enable(self, actor: Actor, agent_id: uuid.UUID) -> dict[str, object]:
        agent = self._agent(actor, agent_id)
        if not actor.has("agents:disable") and not actor.has("agents:manage_all"):
            raise ArError(ErrorCode.FORBIDDEN, "missing permission agents:disable")
        agent["disabled"] = False
        agent["disabled_at"] = None
        agent["disabled_reason"] = None
        agent["updated_at"] = utcnow()
        self._audit(actor, "agent.enabled", agent_id, {})
        self._event("agent.enabled", {"agent_id": str(agent_id)})
        return self.detail(agent, actor)

    def _cancel_runs(self, agent_id: uuid.UUID) -> None:
        now = utcnow()
        for run in self.store.runs.values():
            if run.get("agent_id") != agent_id or run.get("status") not in _ACTIVE:
                continue
            run["status"] = "cancelled"
            run["ended_at"] = now
            conversation = self.store.conversations.get(run.get("conversation_id"))
            if isinstance(conversation, dict) and conversation.get("active_run_id") == run.get(
                "id"
            ):
                conversation["active_run_id"] = None

    def where_used(self, actor: Actor, agent_id: uuid.UUID) -> dict[str, object]:
        agent = self._agent(actor, agent_id)
        if not can_edit(agent, actor):
            raise ArError(ErrorCode.FORBIDDEN, "you cannot view where this agent is used")
        slug = str(agent.get("slug"))
        routines: list[dict[str, object]] = []
        channels: list[dict[str, object]] = []
        for row in self.store.catalogue.values():
            if row.get("tenant_id") != actor.tenant_id:
                continue
            if row.get("kind") == "Routine" and row.get("agent") == slug:
                routines.append({"name": row.get("key")})
            if row.get("kind") == "ChannelIntegration" and row.get("agent") == slug:
                channels.append({"name": row.get("key")})
        parents = [
            {"agent_version_id": str(binding.get("agent_version_id"))}
            for binding in self.store.bindings.values()
            if binding.get("kind") == "subagent" and binding.get("target_key") == slug
        ]
        return {"routines": routines, "channel_integrations": channels, "parent_agents": parents}

    def versions(self, actor: Actor, agent_id: uuid.UUID) -> list[dict[str, object]]:
        agent = self._agent(actor, agent_id)
        editor = can_edit(agent, actor)
        rows = [row for row in self.store.versions.values() if row.get("agent_id") == agent_id]
        if not editor:
            rows = [row for row in rows if row.get("state") == "published"]
        rows.sort(
            key=lambda item: int(item["version"]) if isinstance(item.get("version"), int) else 0
        )
        return [self._version_out(row, editor=editor) for row in rows]

    def version(self, actor: Actor, agent_id: uuid.UUID, ref: str) -> dict[str, object]:
        agent = self._agent(actor, agent_id)
        editor = can_edit(agent, actor)
        if not editor and ref not in {"published"} and not ref.isdigit():
            raise NotFoundError()
        row = self._version(agent, ref)
        if not editor and row.get("state") != "published":
            raise NotFoundError()
        return self._version_out(row, editor=editor)

    def set_favourite(
        self, actor: Actor, agent_id: uuid.UUID, *, favourite: bool
    ) -> dict[str, object]:
        agent = self._agent(actor, agent_id)
        key = (actor.tenant_id, actor.user_id)
        current = set(self.store.favourites.get(key, set()))
        if favourite:
            current.add(agent_id)
        else:
            current.discard(agent_id)
        self.store.favourites[key] = current
        return self.summary(agent, actor)

    def assert_runnable(self, tenant_id: uuid.UUID, agent_id: uuid.UUID) -> None:
        agent = self.store.agents.get(agent_id)
        if not isinstance(agent, dict) or agent.get("tenant_id") != tenant_id:
            raise NotFoundError("agent not found")
        if agent.get("disabled"):
            raise ArError(ErrorCode.RESOURCE_DISABLED, "agent is disabled")

    def open_preview(self, actor: Actor, agent_version_id: uuid.UUID) -> dict[str, object]:
        """A draft version opens a preview conversation for editors only."""
        version = self.store.versions.get(agent_version_id)
        if not isinstance(version, dict) or version.get("tenant_id") != actor.tenant_id:
            raise NotFoundError()
        agent = self.store.agents.get(version.get("agent_id"))
        if not isinstance(agent, dict) or not can_see(agent, actor):
            raise NotFoundError()
        preview = version.get("state") != "published"
        if preview and not can_edit(agent, actor):
            raise NotFoundError()
        if agent.get("disabled"):
            raise ArError(ErrorCode.RESOURCE_DISABLED, "agent is disabled")
        now = utcnow()
        conversation_id = new_id()
        row = {
            "id": conversation_id,
            "tenant_id": actor.tenant_id,
            "user_id": actor.user_id,
            "agent_id": agent["id"],
            "agent_name": agent["name"],
            "agent_version_id": agent_version_id,
            "title": "Preview",
            "status": "active",
            "pinned": False,
            "is_preview": preview,
            "active_run_id": None,
            "created_at": now,
            "updated_at": now,
            "deleted_at": None,
        }
        self.store.conversations[conversation_id] = row
        return cast("dict[str, object]", self.store._public(row))

    def _audit(
        self, actor: Actor, action: str, target_id: object, detail: dict[str, object]
    ) -> None:
        self.store.audit_log.append(
            {
                "tenant_id": str(actor.tenant_id),
                "actor_id": str(actor.user_id),
                "action": action,
                "target_type": "agent",
                "target_id": str(target_id),
                "detail": detail,
                "outcome": "success",
                "at": utcnow().isoformat(),
            }
        )

    def _event(self, topic: str, payload: dict[str, JsonValue]) -> None:
        self.store.domain_events.append(
            {"topic": topic, "payload": payload, "at": utcnow().isoformat()}
        )

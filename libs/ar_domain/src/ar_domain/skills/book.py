"""Skill catalogue on the process store. Spec: docs/03-specs/14-skills.md §3.

HTTP state stays in the process store until M10 (OQ-40). Revision 0016 is the
durable path.
"""

import uuid
from typing import TYPE_CHECKING, cast

from ar_common.errors import ArError, ConflictError, ErrorCode, NotFoundError, ValidationFailedError
from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_domain.audit.memory import remember
from ar_domain.skills.logic import (
    MAX_ASSET_BYTES,
    MAX_ASSET_TOTAL,
    MAX_ASSETS,
    MAX_DESCRIPTION_CHARS,
    MAX_INSTRUCTION_CHARS,
    MAX_SKILLS_PER_TENANT,
    as_int,
    asset_path_error,
    file_sha256,
    skill_hash,
    valid_slug,
)
from ar_domain.skills.metrics import SKILL_PUBLISH

if TYPE_CHECKING:
    from typing import Any

    from ar_domain.agents.access import Actor


class SkillBook:
    """Create, publish and find skills for one tenant."""

    def __init__(self, store: Any) -> None:
        self.store = store

    def list_skills(
        self,
        actor: Actor,
        *,
        query: str = "",
        status: str = "",
        owner: str = "",
        team_id: uuid.UUID | None = None,
    ) -> list[dict[str, object]]:
        rows = [
            self._summary(row)
            for row in self._rows().values()
            if self._visible(row, actor)
            and self._matches(row, query, status, owner, team_id, actor)
        ]
        rows.sort(key=lambda item: str(item.get("name")))
        return rows

    def create(self, actor: Actor, body: dict[str, object]) -> dict[str, object]:
        if not actor.has("skills:create") and not actor.has("skills:manage_all"):
            raise ArError(ErrorCode.FORBIDDEN, "missing permission skills:create")
        slug = str(body.get("slug") or "")
        name = str(body.get("name") or "").strip()
        description = str(body.get("description") or "")
        instructions = str(body.get("instructions_md") or "")
        self._check_new(actor, slug, name, description, instructions)
        now = utcnow()
        skill_id = new_id()
        version_id = new_id()
        assets = self._assets(actor, body.get("assets"))
        tools = self._tools(body.get("required_tools"))
        skill = {
            "id": skill_id,
            "tenant_id": actor.tenant_id,
            "slug": slug,
            "name": name,
            "description": description,
            "owner_user_id": actor.user_id,
            "owner_team_id": body.get("owner_team_id"),
            "visibility": str(body.get("visibility") or "tenant"),
            "status": "draft",
            "published_version_id": None,
            "created_at": now,
            "updated_at": now,
        }
        self._rows()[skill_id] = skill
        self._versions()[version_id] = self._version_row(
            version_id,
            skill,
            0,
            instructions,
            assets,
            tools,
            actor.user_id,
        )
        self._audit(actor, "skill.created", skill_id, {"slug": slug})
        return self.detail(actor, skill_id)

    def detail(self, actor: Actor, skill_id: uuid.UUID) -> dict[str, object]:
        skill = self._get(actor, skill_id)
        body = self._summary(skill)
        draft = self._draft(skill_id)
        published = self._published(skill)
        if self._editor(skill, actor) and draft is not None:
            body["draft"] = self._version_out(draft)
        else:
            body["draft"] = None
        body["published"] = None if published is None else self._version_out(published)
        return body

    def patch(
        self, actor: Actor, skill_id: uuid.UUID, body: dict[str, object]
    ) -> dict[str, object]:
        skill = self._get(actor, skill_id)
        if not self._editor(skill, actor):
            raise ArError(ErrorCode.FORBIDDEN, "you cannot edit this skill")
        if skill.get("status") == "archived":
            raise ArError(ErrorCode.INVALID_STATE, "archived skills cannot be edited")
        draft = self._ensure_draft(skill, actor)
        if "name" in body:
            name = str(body.get("name") or "").strip()
            if not name:
                raise ValidationFailedError("name is required")
            skill["name"] = name
        if "description" in body:
            description = str(body.get("description") or "")
            if len(description) > MAX_DESCRIPTION_CHARS:
                raise ValidationFailedError("description is longer than 500 characters")
            skill["description"] = description
        if "visibility" in body:
            skill["visibility"] = str(body.get("visibility") or "tenant")
        if "owner_team_id" in body:
            skill["owner_team_id"] = body.get("owner_team_id")
        if "instructions_md" in body:
            instructions = str(body.get("instructions_md") or "")
            if len(instructions) > MAX_INSTRUCTION_CHARS:
                raise ValidationFailedError("instructions are longer than 50000 characters")
            draft["instructions_md"] = instructions
        if "required_tools" in body:
            draft["required_tools"] = self._tools(body.get("required_tools"))
        if "assets" in body:
            draft["assets"] = self._assets(actor, body.get("assets"))
        draft["hash"] = skill_hash(
            str(draft.get("instructions_md") or ""),
            _dicts(draft.get("assets")),
            _strings(draft.get("required_tools")),
        )
        skill["updated_at"] = utcnow()
        self._audit(actor, "skill.updated", skill_id, {"slug": skill.get("slug")})
        return self.detail(actor, skill_id)

    def publish(
        self, actor: Actor, skill_id: uuid.UUID, *, change_note: str = ""
    ) -> dict[str, object]:
        skill = self._get(actor, skill_id)
        if not self._editor(skill, actor):
            raise ArError(ErrorCode.FORBIDDEN, "you cannot publish this skill")
        draft = self._draft(skill_id)
        if draft is None:
            raise ArError(ErrorCode.INVALID_STATE, "nothing to publish")
        instructions = str(draft.get("instructions_md") or "")
        if not instructions.strip():
            raise ValidationFailedError("instructions are required")
        tools = _strings(draft.get("required_tools"))
        self._require_tools(tools)
        assets = _dicts(draft.get("assets"))
        version_no = self._next_version(skill_id)
        version_id = new_id()
        row = self._version_row(
            version_id,
            skill,
            version_no,
            instructions,
            assets,
            tools,
            actor.user_id,
        )
        self._versions()[version_id] = row
        skill["published_version_id"] = version_id
        skill["status"] = "published"
        skill["updated_at"] = utcnow()
        self._audit(
            actor,
            "skill.published",
            skill_id,
            {"slug": skill.get("slug"), "version": version_no, "change_note": change_note},
        )
        self.store.domain_events.append(
            {
                "topic": "skill.published",
                "skill_id": str(skill_id),
                "skill_version_id": str(version_id),
                "version": version_no,
            }
        )
        SKILL_PUBLISH.inc()
        return self.detail(actor, skill_id)

    def archive(self, actor: Actor, skill_id: uuid.UUID) -> dict[str, object]:
        skill = self._get(actor, skill_id)
        if not self._editor(skill, actor):
            raise ArError(ErrorCode.FORBIDDEN, "you cannot archive this skill")
        bound = self._published_dependants(actor.tenant_id, str(skill.get("slug")))
        if bound:
            names = ", ".join(str(item.get("slug")) for item in bound)
            raise ConflictError(f"published agents still use this skill: {names}")
        skill["status"] = "archived"
        skill["updated_at"] = utcnow()
        self._audit(actor, "skill.archived", skill_id, {"slug": skill.get("slug")})
        return self.detail(actor, skill_id)

    def versions(self, actor: Actor, skill_id: uuid.UUID) -> list[dict[str, object]]:
        self._get(actor, skill_id)
        rows = [
            self._version_out(row)
            for row in self._versions().values()
            if row.get("skill_id") == skill_id and as_int(row.get("version")) >= 1
        ]
        rows.sort(key=lambda item: as_int(item.get("version")))
        return rows

    def version(self, actor: Actor, skill_id: uuid.UUID, number: int) -> dict[str, object]:
        self._get(actor, skill_id)
        for row in self._versions().values():
            if row.get("skill_id") == skill_id and as_int(row.get("version")) == number:
                return self._version_out(row)
        raise NotFoundError()

    def where_used(self, actor: Actor, skill_id: uuid.UUID) -> dict[str, object]:
        skill = self._get(actor, skill_id)
        latest = self._published(skill)
        latest_id = "" if latest is None else str(latest.get("id"))
        latest_no = 0 if latest is None else as_int(latest.get("version"))
        return {
            "skill_id": str(skill_id),
            "published_version": latest_no or None,
            "agents": self._dependants(actor, str(skill.get("slug")), latest_id),
        }

    def republish_dependants(self, actor: Actor, skill_id: uuid.UUID) -> dict[str, object]:
        skill = self._get(actor, skill_id)
        if not self._editor(skill, actor):
            raise ArError(ErrorCode.FORBIDDEN, "you cannot republish dependants")
        from ar_domain.agents.service import AgentLifecycle  # noqa: PLC0415

        life = AgentLifecycle(self.store)
        slug = str(skill.get("slug"))
        version = self._published(skill)
        number = 0 if version is None else as_int(version.get("version"))
        note = f"Update skill {slug} to v{number}"
        results: list[dict[str, object]] = []
        for item in self._dependants(actor, slug, ""):
            agent_id = uuid.UUID(str(item["agent_id"]))
            if not actor.has("agents:publish") and not actor.has("agents:manage_all"):
                results.append(
                    {"agent_id": str(agent_id), "slug": item.get("slug"), "status": "forbidden"}
                )
                continue
            agent = self.store.agents.get(agent_id)
            version_id = None
            if isinstance(agent, dict):
                version_id = agent.get("published_version_id")
            stored = None
            if version_id is not None:
                stored = self.store.versions.get(version_id)
            definition = stored.get("definition") if isinstance(stored, dict) else None
            if not isinstance(definition, dict):
                results.append(
                    {
                        "agent_id": str(agent_id),
                        "slug": item.get("slug"),
                        "status": "failed",
                        "detail": "missing definition",
                    }
                )
                continue
            try:
                cleaned = {key: value for key, value in definition.items() if key != "resolved"}
                life.save_draft(actor, agent_id, cleaned, change_note=note)
                life.publish(actor, agent_id, change_note=note)
            except (ArError, NotFoundError, ValidationFailedError) as exc:
                results.append(
                    {
                        "agent_id": str(agent_id),
                        "slug": item.get("slug"),
                        "status": "failed",
                        "detail": str(exc),
                    }
                )
                continue
            results.append(
                {"agent_id": str(agent_id), "slug": item.get("slug"), "status": "published"}
            )
        return {"results": results}

    def published_by_slug(self, tenant_id: uuid.UUID, slug: str) -> dict[str, object] | None:
        for row in self._rows().values():
            same_tenant = row.get("tenant_id") == tenant_id and row.get("slug") == slug
            if same_tenant and row.get("status") == "published":
                return row
        return None

    def _check_new(
        self, actor: Actor, slug: str, name: str, description: str, instructions: str
    ) -> None:
        if not valid_slug(slug):
            raise ValidationFailedError("slug is invalid")
        if not name:
            raise ValidationFailedError("name is required")
        if len(description) > MAX_DESCRIPTION_CHARS:
            raise ValidationFailedError("description is longer than 500 characters")
        if len(instructions) > MAX_INSTRUCTION_CHARS:
            raise ValidationFailedError("instructions are longer than 50000 characters")
        owned = [row for row in self._rows().values() if row.get("tenant_id") == actor.tenant_id]
        if len(owned) >= MAX_SKILLS_PER_TENANT:
            raise ArError(ErrorCode.PLAN_LIMIT_REACHED, "skill limit reached")
        if any(row.get("slug") == slug for row in owned):
            raise ConflictError("slug already exists")

    def _assets(self, actor: Actor, raw: object) -> list[dict[str, object]]:
        if raw is None:
            return []
        if not isinstance(raw, list):
            raise ValidationFailedError("assets must be a list")
        if len(raw) > MAX_ASSETS:
            raise ValidationFailedError("a skill can have 50 assets")
        total = 0
        assets: list[dict[str, object]] = []
        for item in raw:
            if not isinstance(item, dict):
                raise ValidationFailedError("asset is invalid")
            path = str(item.get("path") or "")
            reason = asset_path_error(path)
            if reason:
                raise ValidationFailedError(reason)
            file_id = item.get("file_id")
            if not isinstance(file_id, uuid.UUID):
                try:
                    file_id = uuid.UUID(str(item.get("file_id")))
                except ValueError as exc:
                    raise ValidationFailedError("asset file is invalid") from exc
            blob, row = self._file(actor, file_id)
            if len(blob) > MAX_ASSET_BYTES:
                raise ValidationFailedError("an asset is larger than 10 MiB")
            total += len(blob)
            if total > MAX_ASSET_TOTAL:
                raise ValidationFailedError("assets are larger than 50 MiB")
            row["kind"] = "skill_asset"
            assets.append({"path": path, "file_id": file_id, "sha256": file_sha256(blob)})
        return assets

    def _file(self, actor: Actor, file_id: uuid.UUID) -> tuple[bytes, dict[str, object]]:
        row = self.store.files.get(file_id)
        if not isinstance(row, dict) or row.get("tenant_id") != actor.tenant_id:
            raise NotFoundError("asset file was not found")
        blob = self.store.blobs.get(file_id)
        if not isinstance(blob, bytes):
            raise NotFoundError("asset file was not found")
        return blob, row

    def _tools(self, raw: object) -> list[str]:
        return _strings(raw)

    def _require_tools(self, names: list[str]) -> None:
        known = {
            str(row.get("qualified_name"))
            for row in getattr(self.store, "tool_versions", {}).values()
            if isinstance(row, dict)
        }
        missing = [name for name in names if name not in known]
        if missing:
            raise ValidationFailedError(f"unknown tool {missing[0]}")

    def _summary(self, skill: dict[str, object]) -> dict[str, object]:
        published = self._published(skill)
        tools: list[str] = []
        if published is not None:
            tools = _strings(published.get("required_tools"))
        elif (draft := self._draft(skill["id"])) is not None:
            tools = _strings(draft.get("required_tools"))
        return {
            "id": str(skill["id"]),
            "slug": skill.get("slug"),
            "name": skill.get("name"),
            "description": skill.get("description"),
            "visibility": skill.get("visibility"),
            "status": skill.get("status"),
            "owner": None
            if skill.get("owner_user_id") is None
            else {"id": str(skill.get("owner_user_id"))},
            "owner_team": None
            if skill.get("owner_team_id") is None
            else {"id": str(skill.get("owner_team_id"))},
            "published_version": None if published is None else as_int(published.get("version")),
            "required_tools": tools,
            "updated_at": skill.get("updated_at"),
            "used_by_count": len(
                self._published_dependants(skill.get("tenant_id"), str(skill.get("slug")))
            ),
        }

    def _version_out(self, row: dict[str, object]) -> dict[str, object]:
        return {
            "id": str(row["id"]),
            "skill_id": str(row["skill_id"]),
            "version": as_int(row.get("version")),
            "instructions_md": row.get("instructions_md"),
            "assets": row.get("assets") or [],
            "required_tools": row.get("required_tools") or [],
            "hash": row.get("hash"),
            "created_at": row.get("created_at"),
        }

    def _version_row(  # noqa: PLR0917
        self,
        version_id: uuid.UUID,
        skill: dict[str, object],
        number: int,
        instructions: str,
        assets: list[dict[str, object]],
        tools: list[str],
        user_id: uuid.UUID,
    ) -> dict[str, object]:
        return {
            "id": version_id,
            "tenant_id": skill["tenant_id"],
            "skill_id": skill["id"],
            "version": number,
            "instructions_md": instructions,
            "assets": assets,
            "required_tools": tools,
            "hash": skill_hash(instructions, assets, tools),
            "created_by": user_id,
            "created_at": utcnow(),
        }

    def _get(self, actor: Actor, skill_id: uuid.UUID) -> dict[str, object]:
        row = self._rows().get(skill_id)
        if not isinstance(row, dict) or not self._visible(row, actor):
            raise NotFoundError()
        return row

    def _visible(self, skill: dict[str, object], actor: Actor) -> bool:
        if skill.get("tenant_id") != actor.tenant_id:
            return False
        if actor.has("skills:manage_all"):
            return True
        if not actor.has("skills:read") and not actor.has("skills:create"):
            return False
        visibility = str(skill.get("visibility") or "private")
        if visibility == "tenant":
            return True
        if skill.get("owner_user_id") == actor.user_id:
            return True
        team = skill.get("owner_team_id")
        return visibility == "team" and team is not None and str(team) in actor.team_ids

    def _editor(self, skill: dict[str, object], actor: Actor) -> bool:
        if actor.has("skills:manage_all"):
            return True
        return skill.get("owner_user_id") == actor.user_id

    def _matches(  # noqa: PLR0917
        self,
        skill: dict[str, object],
        query: str,
        status: str,
        owner: str,
        team_id: uuid.UUID | None,
        actor: Actor,
    ) -> bool:
        if status and skill.get("status") != status:
            return False
        if owner == "me" and skill.get("owner_user_id") != actor.user_id:
            return False
        if team_id is not None and skill.get("owner_team_id") != team_id:
            return False
        if not query:
            return True
        haystack = f"{skill.get('name', '')} {skill.get('description', '')} {skill.get('slug', '')}"
        return query.lower() in haystack.lower()

    def _draft(self, skill_id: object) -> dict[str, object] | None:
        for row in self._versions().values():
            if row.get("skill_id") == skill_id and as_int(row.get("version")) == 0:
                return row
        return None

    def _ensure_draft(self, skill: dict[str, object], actor: Actor) -> dict[str, object]:
        found = self._draft(skill["id"])
        if found is not None:
            return found
        published = self._published(skill)
        version_id = new_id()
        row = self._version_row(
            version_id,
            skill,
            0,
            "" if published is None else str(published.get("instructions_md") or ""),
            [] if published is None else _dicts(published.get("assets")),
            [] if published is None else _strings(published.get("required_tools")),
            actor.user_id,
        )
        self._versions()[version_id] = row
        return row

    def _published(self, skill: dict[str, object]) -> dict[str, object] | None:
        version_id = skill.get("published_version_id")
        if not isinstance(version_id, uuid.UUID):
            return None
        row = self._versions().get(version_id)
        return row if isinstance(row, dict) else None

    def _next_version(self, skill_id: uuid.UUID) -> int:
        numbers = [
            as_int(row.get("version"))
            for row in self._versions().values()
            if row.get("skill_id") == skill_id
        ]
        return max(numbers, default=0) + 1

    def _dependants(self, actor: Actor, slug: str, latest_id: str) -> list[dict[str, object]]:
        found: list[dict[str, object]] = []
        for agent in self.store.agents.values():
            if agent.get("tenant_id") != actor.tenant_id:
                continue
            for state, version_id in (
                ("published", agent.get("published_version_id")),
                ("draft", agent.get("draft_version_id")),
            ):
                if not isinstance(version_id, uuid.UUID):
                    continue
                version = self.store.versions.get(version_id)
                definition = version.get("definition") if isinstance(version, dict) else None
                if not isinstance(definition, dict) or not _uses(definition, slug):
                    continue
                pinned = _pinned(definition, slug)
                found.append(
                    {
                        "agent_id": str(agent.get("id")),
                        "slug": agent.get("slug"),
                        "name": agent.get("name"),
                        "state": state,
                        "skill_version_id": pinned,
                        "update_available": bool(latest_id and pinned and pinned != latest_id)
                        or (state == "published" and bool(latest_id) and pinned != latest_id),
                    }
                )
        return found

    def _published_dependants(self, tenant_id: object, slug: str) -> list[dict[str, object]]:
        found: list[dict[str, object]] = []
        for agent in getattr(self.store, "agents", {}).values():
            if agent.get("tenant_id") != tenant_id or agent.get("status") != "published":
                continue
            version_id = agent.get("published_version_id")
            version = None
            if isinstance(version_id, uuid.UUID):
                version = self.store.versions.get(version_id)
            definition = version.get("definition") if isinstance(version, dict) else None
            if isinstance(definition, dict) and _uses(definition, slug):
                found.append(agent)
        return found

    def _rows(self) -> dict[uuid.UUID, dict[str, object]]:
        if not hasattr(self.store, "skills"):
            self.store.skills = {}
        return cast("dict[uuid.UUID, dict[str, object]]", self.store.skills)

    def _versions(self) -> dict[uuid.UUID, dict[str, object]]:
        if not hasattr(self.store, "skill_versions"):
            self.store.skill_versions = {}
        return cast("dict[uuid.UUID, dict[str, object]]", self.store.skill_versions)

    def _audit(self, actor: Actor, action: str, target: object, detail: dict[str, object]) -> None:
        remember(
            self.store,
            tenant_id=actor.tenant_id,
            actor_id=actor.user_id,
            action=action,
            target_type="skill",
            target_id=target,
            detail=detail,
        )


def _strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item)]


def _dicts(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _uses(definition: dict[str, object], slug: str) -> bool:
    skills = definition.get("skills")
    if not isinstance(skills, list):
        return False
    return any(str(item).split("@", 1)[0] == slug for item in skills)


def _pinned(definition: dict[str, object], slug: str) -> str:
    resolved = definition.get("resolved")
    skills = resolved.get("skills") if isinstance(resolved, dict) else None
    if not isinstance(skills, list):
        return ""
    for item in skills:
        if isinstance(item, dict) and str(item.get("slug")) == slug:
            return str(item.get("skill_version_id") or item.get("skillVersionId") or "")
    return ""

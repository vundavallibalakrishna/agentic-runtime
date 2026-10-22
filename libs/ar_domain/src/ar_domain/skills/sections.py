"""Capabilities index and loaded-skill blocks. Spec: docs/03-specs/07-agent-runtime.md §4."""

import uuid
from typing import TYPE_CHECKING

from ar_domain.skills.book import SkillBook
from ar_domain.skills.logic import split_skill_ref

if TYPE_CHECKING:
    from typing import Any


def capabilities_block(
    store: Any, definition: dict[str, object], *, tenant_id: uuid.UUID | None = None
) -> str:
    """Block 3: skills, knowledge, subagents and whether a computer is available."""
    lines: list[str] = []
    tenant = tenant_id
    book = SkillBook(store)
    for raw in _strings(definition.get("skills")):
        slug, _constraint = split_skill_ref(raw)
        skill = book.published_by_slug(tenant, slug) if tenant is not None else None
        description = "" if skill is None else str(skill.get("description") or "")
        lines.append(f"- {slug}: {description}".rstrip())
    knowledge = definition.get("knowledge")
    collections = knowledge.get("collections") if isinstance(knowledge, dict) else []
    for slug in _strings(collections):
        description = _collection_description(store, slug)
        lines.append(f"- collection {slug}: {description}".rstrip())
    subagents = definition.get("subagents")
    allowed = subagents.get("allowed") if isinstance(subagents, dict) else []
    lines.extend(
        f"- subagent {slug}: {_agent_description(store, slug)}" for slug in _strings(allowed)
    )
    sandbox = definition.get("sandbox")
    if isinstance(sandbox, dict) and sandbox.get("enabled") is True:
        lines.append("- computer: available")
    if not lines:
        return ""
    return "Capabilities:\n" + "\n".join(lines)


def loaded_skills_block(store: Any, conversation: dict[str, object], run: dict[str, object]) -> str:
    """Block 4. Child runs keep their own loaded list."""
    depth = run.get("depth")
    source = run if isinstance(depth, int) and depth > 0 else conversation
    loaded = source.get("loaded_skills")
    if not isinstance(loaded, list) or not loaded:
        return ""
    parts: list[str] = []
    for item in loaded:
        if not isinstance(item, dict):
            continue
        text = _instructions(store, item)
        if text:
            parts.append(text)
    return "\n\n".join(parts)


def _instructions(store: Any, item: dict[str, object]) -> str:
    version_id = item.get("version_id") or item.get("skill_version_id")
    row = None
    if isinstance(version_id, uuid.UUID):
        found = store.skill_versions.get(version_id)
        row = found if isinstance(found, dict) else None
    if row is None:
        return ""
    return str(row.get("instructions_md") or "")[:50_000]


def _collection_description(store: Any, slug: str) -> str:
    for row in getattr(store, "knowledge_collections", {}).values():
        if isinstance(row, dict) and row.get("slug") == slug:
            return str(row.get("description") or row.get("name") or "")
    return ""


def _agent_description(store: Any, slug: str) -> str:
    for row in getattr(store, "agents", {}).values():
        if isinstance(row, dict) and row.get("slug") == slug:
            return str(row.get("description") or row.get("name") or slug)
    return slug


def _strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item)]

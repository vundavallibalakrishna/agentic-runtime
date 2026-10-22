"""Load a skill into a run and copy assets onto the computer.

Spec: docs/03-specs/14-skills.md §4. Instructions are trusted author content.
"""

import uuid
import zipfile
from io import BytesIO
from typing import TYPE_CHECKING
from xml.sax.saxutils import escape

from ar_common.sandboxkit import confine
from ar_domain.sandboxes.runtime import ensure_scope, run_tool, workspace_root
from ar_domain.skills.book import SkillBook
from ar_domain.skills.logic import as_int, highest_match, split_skill_ref
from ar_domain.skills.metrics import SKILL_LOADS

if TYPE_CHECKING:
    from typing import Any


def load_skill(store: Any, run: dict[str, object], raw_slug: str) -> dict[str, object]:
    """Return instructions and an asset manifest. Assets land under ``.skills``."""
    slug, constraint = split_skill_ref(raw_slug)
    tenant = run.get("tenant_id")
    if not isinstance(tenant, uuid.UUID):
        return _error("validation_failed", "skill load needs a tenant")
    book = SkillBook(store)
    skill = book.published_by_slug(tenant, slug)
    if skill is None:
        return _error("not_found", f"unknown skill {slug}")
    version = _resolve(store, skill, constraint)
    if version is None:
        return _error("not_found", f"skill {slug} has no matching version")
    definition = _definition(store, run)
    if not _agent_has_tools(store, definition, _strings(version.get("required_tools"))):
        return _error("validation_failed", "this agent does not have the tools the skill needs")
    instructions = str(version.get("instructions_md") or "")[:50_000]
    manifest = _write_assets(store, run, skill, version)
    _remember(store, run, skill, version)
    SKILL_LOADS.labels(skill=slug).inc()
    lines = [f"{item.get('path')} ({str(item.get('sha256') or '')[:12]})" for item in manifest]
    text = instructions
    if lines:
        text = instructions + "\n\nAssets:\n" + "\n".join(lines)
    return {
        "text": text,
        "structured": {
            "skill": slug,
            "version": as_int(version.get("version")),
            "instructions_md": instructions,
            "assets": manifest,
        },
        "is_error": False,
    }


def write_docx(store: Any, run: dict[str, object], *, title: str, body: str) -> dict[str, object]:
    """Write a DOCX into the computer and export it as an artifact."""
    sandbox = _ensure(store, run)
    if sandbox is None:
        return _error("sandbox_unavailable", "the computer is not ready")
    root = workspace_root(uuid.UUID(str(sandbox["id"])))
    target = confine(root, "/workspace/outputs/brand-brief.docx")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(docx_bytes(title, body))
    return run_tool(
        store,
        "export_file",
        {
            "path": "/workspace/outputs/brand-brief.docx",
            "_tenant_id": run.get("tenant_id"),
            "_user_id": run.get("user_id"),
            "_agent_id": run.get("agent_id"),
            "_run_id": run.get("id"),
            "_conversation_id": run.get("conversation_id"),
        },
    )


def docx_bytes(title: str, body: str) -> bytes:
    """A small Office Open XML document. No extra wheel is required."""
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body><w:p><w:r><w:t>{escape(title)}</w:t></w:r></w:p>"
        f"<w:p><w:r><w:t>{escape(body)}</w:t></w:r></w:p></w:body></w:document>"
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" '
        'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.'
        'wordprocessingml.document.main+xml"/>'
        "</Types>"
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="word/document.xml"/>'
        "</Relationships>"
    )
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", rels)
        archive.writestr("word/document.xml", document)
    return buffer.getvalue()


def _resolve(store: Any, skill: dict[str, object], constraint: str) -> dict[str, object] | None:
    versions = [
        as_int(row.get("version"))
        for row in store.skill_versions.values()
        if row.get("skill_id") == skill.get("id") and as_int(row.get("version")) >= 1
    ]
    chosen = highest_match(versions, constraint)
    if chosen is None:
        published_id = skill.get("published_version_id")
        row = (
            store.skill_versions.get(published_id) if isinstance(published_id, uuid.UUID) else None
        )
        return row if isinstance(row, dict) else None
    for row in store.skill_versions.values():
        if not isinstance(row, dict):
            continue
        if row.get("skill_id") == skill.get("id") and as_int(row.get("version")) == chosen:
            return row
    return None


def _write_assets(
    store: Any,
    run: dict[str, object],
    skill: dict[str, object],
    version: dict[str, object],
) -> list[dict[str, object]]:
    assets = version.get("assets")
    if not isinstance(assets, list) or not assets:
        return []
    definition = _definition(store, run)
    sandbox_spec = definition.get("sandbox") if isinstance(definition, dict) else None
    enabled = isinstance(sandbox_spec, dict) and sandbox_spec.get("enabled") is True
    if not enabled and run.get("sandbox_id") is None:
        return [
            {
                "path": str(item.get("path")),
                "sha256": str(item.get("sha256") or ""),
                "mounted": False,
            }
            for item in assets
            if isinstance(item, dict)
        ]
    sandbox = _ensure(store, run)
    if sandbox is None:
        return []
    root = workspace_root(uuid.UUID(str(sandbox["id"])))
    slug = str(skill.get("slug"))
    manifest: list[dict[str, object]] = []
    for item in assets:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or "")
        file_id = item.get("file_id")
        blob = store.blobs.get(file_id) if isinstance(file_id, uuid.UUID) else None
        if not isinstance(blob, bytes):
            continue
        target = confine(root, f"/workspace/.skills/{slug}/{path}")
        digest = str(item.get("sha256") or "")
        if target.is_file() and target.read_bytes() == blob:
            mounted = True
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(blob)
            mounted = True
        manifest.append({"path": path, "sha256": digest, "mounted": mounted})
    return manifest


def _ensure(store: Any, run: dict[str, object]) -> dict[str, object] | None:
    tenant = run.get("tenant_id")
    user = run.get("user_id")
    conversation = run.get("conversation_id")
    agent_id = run.get("agent_id")
    if not isinstance(tenant, uuid.UUID):
        return None
    try:
        return ensure_scope(
            store,
            tenant_id=tenant,
            template_slug="default",
            scope="conversation",
            scope_key=str(conversation),
            conversation_id=conversation if isinstance(conversation, uuid.UUID) else None,
            agent_id=agent_id if isinstance(agent_id, uuid.UUID) else None,
            user_id=user if isinstance(user, uuid.UUID) else None,
        )
    except LookupError, RuntimeError:
        return None


def _remember(
    store: Any, run: dict[str, object], skill: dict[str, object], version: dict[str, object]
) -> None:
    ref = {
        "skill_id": str(skill.get("id")),
        "version": as_int(version.get("version")),
        "version_id": version.get("id"),
    }
    depth = run.get("depth")
    if isinstance(depth, int) and depth > 0:
        loaded = run.setdefault("loaded_skills", [])
        if isinstance(loaded, list):
            loaded.append(ref)
        return
    conversation_id = run.get("conversation_id")
    conversation = (
        store.conversations.get(conversation_id) if isinstance(conversation_id, uuid.UUID) else None
    )
    if not isinstance(conversation, dict):
        return
    loaded = conversation.setdefault("loaded_skills", [])
    if isinstance(loaded, list) and ref not in loaded:
        loaded.append(ref)


def _agent_has_tools(store: Any, definition: dict[str, object], required: list[str]) -> bool:
    del store
    if not required:
        return True
    granted: set[str] = set()
    tools = definition.get("tools")
    if isinstance(tools, list):
        for binding in tools:
            if not isinstance(binding, dict):
                continue
            server = str(binding.get("server") or "")
            include = binding.get("include")
            if include in (["*"], "*"):
                granted.add(server)
            elif isinstance(include, list):
                granted.update(f"{server}.{name}" for name in include)
    return all(name in granted or name.split(".", 1)[0] in granted for name in required)


def _definition(store: Any, run: dict[str, object]) -> dict[str, object]:
    version_id = run.get("agent_version_id")
    version = store.versions.get(version_id) if isinstance(version_id, uuid.UUID) else None
    definition = version.get("definition") if isinstance(version, dict) else None
    return definition if isinstance(definition, dict) else {}


def _strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _error(code: str, message: str) -> dict[str, object]:
    return {"text": message, "structured": {}, "is_error": True, "code": code}

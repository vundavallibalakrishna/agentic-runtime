"""Import and export a skill as markdown with front matter, or as a folder zip.

Helper files travel inside the zip. Their text is stored on the skill version
so a restart still has them. A skill does not run code of its own.
"""

from __future__ import annotations

import hashlib
import io
import re
import zipfile
from typing import TYPE_CHECKING, TypedDict

from ar_common.errors import ValidationFailedError
from ar_domain.skills.book import SkillBook
from ar_domain.skills.logic import asset_path_error, file_sha256, valid_slug

if TYPE_CHECKING:
    from typing import Any

    from ar_domain.agents.access import Actor

_FENCE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_LINE = re.compile(r"^([A-Za-z0-9_]+):\s*(.*)$")
_MAX_ZIP = 2_000_000
_MAX_FILE = 200_000


class ParsedSkill(TypedDict):
    name: str
    slug: str
    description: str
    instructions: str
    examples: list[str]
    files: dict[str, str]


def import_skill(
    store: Any, actor: Actor, *, markdown: str = "", archive: bytes = b""
) -> dict[str, object]:
    """Create and publish a skill from markdown or a zip that contains SKILL.md."""
    files: dict[str, str] = {}
    body = markdown
    if archive:
        body, files = _read_zip(archive)
        if markdown.strip():
            body = markdown
    parsed = parse_markdown(body)
    helpers = {**files, **parsed["files"]}
    book = SkillBook(store)
    created = book.create(
        actor,
        {
            "slug": parsed["slug"],
            "name": parsed["name"],
            "description": parsed["description"],
            "instructions_md": parsed["instructions"],
            "visibility": "tenant",
        },
    )
    skill_id = created["id"]
    _attach_files(store, skill_id, helpers, parsed["examples"])
    return book.publish(actor, _uuid(skill_id), change_note="imported")


def export_skill(store: Any, actor: Actor, skill_id: object) -> dict[str, object]:
    """Markdown plus helper files. ``archive_b64`` is a zip a person can unpack."""
    import base64  # noqa: PLC0415
    import uuid  # noqa: PLC0415

    book = SkillBook(store)
    detail = book.detail(actor, uuid.UUID(str(skill_id)))
    version = detail.get("published") or detail.get("draft")
    if not isinstance(version, dict):
        raise ValidationFailedError("this skill has no version to export")
    instructions = str(version.get("instructions_md") or "")
    examples, helpers = _from_assets(version.get("assets"))
    markdown = render_markdown(
        name=str(detail.get("name") or ""),
        slug=str(detail.get("slug") or ""),
        description=str(detail.get("description") or ""),
        examples=examples,
        instructions=instructions,
    )
    archive = _zip(markdown, helpers)
    return {
        "filename": f"{detail.get('slug') or 'skill'}.zip",
        "markdown": markdown,
        "files": [{"path": path, "text": text} for path, text in sorted(helpers.items())],
        "archive_b64": base64.b64encode(archive).decode("ascii"),
    }


def parse_markdown(markdown: str) -> ParsedSkill:
    """Read front matter. The body is the instruction text."""
    match = _FENCE.match(markdown.strip() + "\n" if markdown.endswith("---") else markdown)
    raw = markdown
    meta: dict[str, str] = {}
    if match:
        raw = markdown[match.end() :]
        for line in match.group(1).splitlines():
            found = _LINE.match(line.strip())
            if found:
                meta[found.group(1).lower()] = found.group(2).strip().strip("\"'")
    name = meta.get("name") or _heading(raw) or "Skill"
    description = meta.get("description") or name
    slug = meta.get("slug") or _slug(name)
    if not valid_slug(slug):
        slug = _slug(name)
    if not valid_slug(slug):
        raise ValidationFailedError("the skill name needs a slug of letters and numbers")
    examples = [item.strip() for item in meta.get("examples", "").split("|") if item.strip()]
    instructions = raw.strip()
    if not instructions:
        raise ValidationFailedError("the skill needs instructions")
    return {
        "name": name[:200],
        "slug": slug,
        "description": description[:500],
        "instructions": instructions[:50_000],
        "examples": examples[:8],
        "files": {},
    }


def render_markdown(
    *,
    name: str,
    slug: str,
    description: str,
    examples: list[str],
    instructions: str,
) -> str:
    """Front matter a person can edit and import again."""
    example_line = " | ".join(examples)
    lines = [
        "---",
        f"name: {name}",
        f"slug: {slug}",
        f"description: {description}",
    ]
    if example_line:
        lines.append(f"examples: {example_line}")
    lines.append("---")
    lines.append("")
    lines.append(instructions.strip())
    lines.append("")
    return "\n".join(lines)


def _attach_files(store: Any, skill_id: object, files: dict[str, str], examples: list[str]) -> None:
    import uuid  # noqa: PLC0415

    target = uuid.UUID(str(skill_id))
    assets: list[dict[str, object]] = []
    if examples:
        text = "\n".join(examples)
        assets.append(_asset("examples.txt", text))
    for path, text in files.items():
        if path.lower() in {"skill.md", "examples.txt"}:
            continue
        if asset_path_error(path):
            continue
        assets.append(_asset(path, text))
    for row in store.skill_versions.values():
        version = int(row.get("version") or 0) if isinstance(row, dict) else -1
        if isinstance(row, dict) and row.get("skill_id") == target and version == 0:
            row["assets"] = assets


def _asset(path: str, text: str) -> dict[str, object]:
    data = text.encode()[:_MAX_FILE]
    return {"path": path, "text": data.decode(errors="replace"), "sha256": file_sha256(data)}


def _from_assets(value: object) -> tuple[list[str], dict[str, str]]:
    examples: list[str] = []
    files: dict[str, str] = {}
    if not isinstance(value, list):
        return examples, files
    for item in value:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or "")
        text = str(item.get("text") or "")
        if path == "examples.txt":
            examples = [line.strip() for line in text.splitlines() if line.strip()]
        elif path and text:
            files[path] = text
    return examples, files


def _read_zip(archive: bytes) -> tuple[str, dict[str, str]]:
    if len(archive) > _MAX_ZIP:
        raise ValidationFailedError("the skill archive is larger than 2 MB")
    try:
        book = zipfile.ZipFile(io.BytesIO(archive))
    except zipfile.BadZipFile as exc:
        raise ValidationFailedError("the skill archive is not a zip file") from exc
    markdown = ""
    files: dict[str, str] = {}
    for info in book.infolist():
        if info.is_dir() or info.file_size > _MAX_FILE:
            continue
        name = info.filename.replace("\\", "/").lstrip("/")
        if ".." in name.split("/"):
            continue
        leaf = name.split("/")[-1]
        data = book.read(info)
        text = data.decode("utf-8", errors="replace")
        if leaf.lower() == "skill.md" or (not markdown and leaf.lower().endswith(".md")):
            markdown = text
        elif asset_path_error(leaf) == "":
            files[leaf] = text
    if not markdown:
        raise ValidationFailedError("the archive needs a SKILL.md or a markdown file")
    return markdown, files


def _zip(markdown: str, files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as book:
        book.writestr("SKILL.md", markdown)
        for path, text in files.items():
            book.writestr(path, text)
    return buffer.getvalue()


def _heading(markdown: str) -> str:
    for line in markdown.splitlines():
        cleaned = line.strip()
        if cleaned.startswith("#"):
            return cleaned.lstrip("#").strip()
    return ""


def _slug(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:62]
    if len(slug) < 2:
        digest = hashlib.sha256(name.encode()).hexdigest()[:6]
        slug = f"skill-{digest}"
    return slug


def _uuid(value: object) -> Any:
    import uuid  # noqa: PLC0415

    return uuid.UUID(str(value))

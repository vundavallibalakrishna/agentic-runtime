"""Skill hash, asset paths, version constraints and subagent cycles.

Spec: docs/03-specs/14-skills.md and docs/03-specs/07-agent-runtime.md §7.
"""

import hashlib
import os
import re
from typing import cast

from pydantic import JsonValue

from ar_common.jcs import canonical_json

_PATH = re.compile(r"^[A-Za-z0-9._/-]{1,200}$")
_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}$")
_CONSTRAINT = re.compile(r"^(\^|~)?(\d+)(?:\.(\d+))?(?:\.(\d+))?$|^\*$")
MAX_SKILLS_PER_TENANT = 500
MAX_SKILLS_PER_AGENT = 30
MAX_ASSETS = 50
MAX_ASSET_BYTES = 10 * 1024 * 1024
MAX_ASSET_TOTAL = 50 * 1024 * 1024
MAX_INSTRUCTION_CHARS = 50_000
MAX_DESCRIPTION_CHARS = 500
PLATFORM_MAX_DEPTH = 3

_BUDGET_KEYS = (
    "max_steps",
    "max_tokens",
    "max_cost_micros",
    "max_wall_clock_s",
    "max_tool_calls",
    "max_parallel_tool_calls",
)


def valid_slug(value: str) -> bool:
    """True when ``value`` is a skill or agent slug."""
    return _SLUG.fullmatch(value) is not None


def asset_path_error(path: str) -> str:
    """Return a reason the asset path is rejected, or an empty string."""
    if not _PATH.fullmatch(path) or ".." in path.split("/") or path.startswith("/"):
        return "asset path must be a relative file name"
    return ""


def skill_hash(instructions: str, assets: list[dict[str, object]], tools: list[str]) -> str:
    """sha256 of the JCS document named in spec 14 §3."""
    rows = sorted(
        (
            {"path": str(item.get("path") or ""), "sha256": str(item.get("sha256") or "")}
            for item in assets
        ),
        key=lambda item: str(item["path"]),
    )
    document = {
        "assets": rows,
        "instructions_md": instructions,
        "required_tools": sorted(tools),
    }
    return hashlib.sha256(canonical_json(cast("JsonValue", document))).hexdigest()


def file_sha256(data: bytes) -> str:
    """Hex digest of an asset body."""
    return hashlib.sha256(data).hexdigest()


def split_skill_ref(raw: str) -> tuple[str, str]:
    """Split ``slug`` or ``slug@^1`` into a slug and a constraint."""
    if "@" not in raw:
        return raw, ""
    slug, constraint = raw.split("@", 1)
    return slug, constraint


def parse_constraint(constraint: str) -> tuple[str, int, int | None] | None:
    """Return ``(op, major, minor)`` or None when the constraint is not usable.

    An empty constraint means the latest published version. ``*`` matches any
    published version. ``^1`` matches major 1. Integer skill versions are majors.
    """
    if constraint in {"", "*"}:
        return ("*", 0, None)
    match = _CONSTRAINT.fullmatch(constraint)
    if match is None or match.group(2) is None:
        return None
    op = match.group(1) or "="
    major = int(match.group(2))
    minor = int(match.group(3)) if match.group(3) is not None else None
    return (op, major, minor)


def constraint_matches(version: int, constraint: str) -> bool:
    """True when an integer skill version satisfies the constraint."""
    parsed = parse_constraint(constraint)
    if parsed is None or version < 1:
        return False
    op, major, minor = parsed
    if op == "*":
        return True
    if op == "=":
        return version == major and (minor is None or minor == 0)
    if op == "~":
        return version == major
    return version == major


def highest_match(versions: tuple[int, ...] | list[int], constraint: str) -> int | None:
    """Highest published version that satisfies ``constraint``."""
    matched = [version for version in versions if constraint_matches(version, constraint)]
    if not matched:
        return None
    return max(matched)


def reaches(start: str, target: str, edges: dict[str, tuple[str, ...]]) -> bool:
    """True when ``target`` is reachable from ``start`` in the published graph."""
    if not target:
        return False
    seen: set[str] = set()
    stack = [start]
    while stack:
        node = stack.pop()
        if node == target:
            return True
        if node in seen:
            continue
        seen.add(node)
        stack.extend(edges.get(node, ()))
    return False


def chain_too_deep(
    slug: str,
    allowed: list[str],
    edges: dict[str, tuple[str, ...]],
    max_depth: int,
) -> bool:
    """True when a delegation chain from ``slug`` is deeper than ``max_depth``."""
    graph = dict(edges)
    graph[slug] = tuple(allowed)
    layer = [slug]
    seen = {slug}
    for depth in range(1, max_depth + 2):
        nxt: list[str] = []
        for node in layer:
            for child in graph.get(node, ()):
                if child not in seen:
                    seen.add(child)
                    nxt.append(child)
        if not nxt:
            return False
        if depth > max_depth:
            return True
        layer = nxt
    return False


def platform_max_depth() -> int:
    """``AR_MAX_DEPTH``, capped at the platform maximum of 3."""
    raw = os.environ.get("AR_MAX_DEPTH", "3")
    if raw.isdigit():
        return min(int(raw), PLATFORM_MAX_DEPTH)
    return PLATFORM_MAX_DEPTH


def child_budget(child: dict[str, object], remaining: dict[str, object]) -> dict[str, int]:
    """Element-wise minimum of the child definition budget and the parent remainder."""
    out: dict[str, int] = {}
    for key in _BUDGET_KEYS:
        left = _count(child.get(key))
        right = _count(remaining.get(key))
        if key not in child and key not in remaining:
            continue
        if key not in remaining:
            out[key] = left
        elif key not in child:
            out[key] = right
        else:
            out[key] = min(left, right)
    return out


def budget_exhausted(remaining: dict[str, object]) -> str:
    """Return the first exhausted limit name, or an empty string."""
    for key in ("max_steps", "max_tokens", "max_cost_micros", "max_wall_clock_s", "max_tool_calls"):
        if key in remaining and _count(remaining.get(key)) <= 0:
            return key
    return ""


def as_int(value: object) -> int:
    """Integer fields on untyped rows. Booleans and other types count as zero."""
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return value


def _count(value: object) -> int:
    return as_int(value)

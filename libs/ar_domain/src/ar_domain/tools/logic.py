"""Pure tool-registry decisions. Spec: docs/03-specs/08-tool-registry-mcp.md."""

import hashlib
import math
import random
import re
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import Mapping

import orjson
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from pydantic import JsonValue

from ar_common.jcs import args_hash

_SLUG = re.compile(r"^[a-z][a-z0-9_]{1,30}$")
_NAME = re.compile(r"^[a-z][a-z0-9_]{0,47}$")
_SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
_RANK = {"public": 0, "internal": 1, "confidential": 2, "restricted": 3}
_ALLOWED = frozenset({"R0", "R1", "W1"})


def slug_ok(value: str) -> bool:
    return _SLUG.match(value) is not None


def name_ok(value: str) -> bool:
    return _NAME.match(value) is not None


def semver_key(value: str) -> tuple[int, int, int] | None:
    match = _SEMVER.match(value)
    if match is None:
        return None
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def semver_greater(candidate: str, existing: list[str]) -> bool:
    key = semver_key(candidate)
    if key is None:
        return False
    return all(
        prior is not None and key > prior for prior in (semver_key(item) for item in existing)
    )


def description_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def call_args_hash(tool_version_id: str, arguments: dict[str, object]) -> str:
    """sha256 of JCS({tool_version_id, arguments})."""
    payload: dict[str, JsonValue] = {
        "arguments": cast("JsonValue", arguments),
        "tool_version_id": tool_version_id,
    }
    return args_hash(payload)


def manifest_hash(manifest: Mapping[str, object]) -> str:
    return args_hash(cast("JsonValue", dict(manifest)))


def as_mapping(value: object) -> dict[str, object]:
    """Copy a JSON object. Anything else becomes an empty mapping."""
    if isinstance(value, dict):
        return {str(key): item for key, item in value.items()}
    return {}


def as_sequence(value: object) -> list[object]:
    """Copy a JSON array. Anything else becomes an empty list."""
    if isinstance(value, list):
        return list(value)
    return []


def as_int(value: object, default: int) -> int:
    """Read an integer, or return ``default``."""
    if isinstance(value, bool) or value is None:
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    return default


def propose_risk(  # noqa: PLR0911
    kind: str, *, method: str = "", annotations: dict[str, object] | None = None
) -> str:
    """Map a discovered tool onto a risk class. Spec 08 §7."""
    notes = annotations or {}
    if notes.get("destructiveHint") is True:
        return "W3"
    if kind == "sql":
        return "R1"
    if kind == "openapi":
        verb = method.upper()
        if verb in {"GET", "HEAD"}:
            return "R0"
        if verb == "DELETE":
            return "W3"
        if verb in {"POST", "PUT", "PATCH"}:
            return "W2"
        return "R1"
    if kind == "remote_mcp":
        # A server must mark a tool read-only. Anything else waits for approval.
        if notes.get("readOnlyHint") is True:
            return "R0"
        return "W2"
    if notes.get("readOnlyHint") is True:
        return "R0"
    return "R1"


def interim_decision(risk_class: str) -> tuple[str, str]:
    """Allow R0/R1/W1. W2/W3 wait for approvals (OQ-06)."""
    if risk_class in _ALLOWED:
        return "allow", ""
    return "deny", "approvals are not enabled yet"


def schema_errors(schema: dict[str, object], arguments: dict[str, object]) -> str | None:
    """Return a compact message when arguments do not match the tool schema."""
    try:
        validator = Draft202012Validator(schema)
    except SchemaError as exc:
        return f"invalid schema: {exc.message}"
    errors = sorted(validator.iter_errors(arguments), key=lambda item: list(item.path))
    if not errors:
        return None
    first = errors[0]
    loc = ".".join(str(part) for part in first.path) or "$"
    return f"{loc}: {first.message}"


def clearance_allows(tool_class: str, user_class: str) -> bool:
    return _RANK.get(tool_class, 1) <= _RANK.get(user_class, 2)


def hash_embedding(text: str, dimensions: int = 1024) -> list[float]:
    """Deterministic unit vector. The embed alias replaces this when the gateway is wired."""
    seed = int.from_bytes(hashlib.sha256(text.encode()).digest()[:8], "big")
    rng = random.Random(seed)  # noqa: S311 — stable tool search, not a secret
    raw = [rng.uniform(-1.0, 1.0) for _ in range(dimensions)]
    norm = math.sqrt(sum(item * item for item in raw)) or 1.0
    return [item / norm for item in raw]


def cosine(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    return sum(a * b for a, b in zip(left, right, strict=True))


def redact(value: dict[str, object]) -> dict[str, object]:
    """Drop obvious secret keys before a tool call is stored."""
    hidden = {"password", "token", "secret", "api_key", "authorization", "dsn"}
    clean: dict[str, object] = {}
    for key, item in value.items():
        if key.lower() in hidden:
            clean[key] = "[redacted]"
        else:
            clean[key] = item
    return clean


def preview(text: str, limit: int = 2048) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def dumps(value: object) -> str:
    return orjson.dumps(value).decode()

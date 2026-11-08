#!/usr/bin/env python
"""Invoke every registered tool through the real pipeline and report its working state.

Layer 1 of the platform verification plan (2026-11-08): answer "is every tool in a working
state?" with data, not by reading the code. Each tool is called via ``ToolPipeline.execute``
— the same path the gateway uses, with entitlement, schema validation, policy, dispatch and
audit — using arguments generated from its own input schema, and the outcome is classified.

Run (fixtures + no model):      uv run python scripts/tool_matrix.py
Run (with a real model):        AR_TOOL_MATRIX_LIVE=1 AR_CERT_LLM_API_KEY=... \
                                AR_CERT_LLM_BASE_URL=... AR_CERT_LLM_MODEL=... \
                                uv run python scripts/tool_matrix.py

It writes docs/testing/tool-matrix/report.md and prints a summary. It never prints secrets.
"""

from __future__ import annotations

import os
import sys
import uuid
from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING

from ar_domain.chat.service import demo_id
from ar_domain.tools.pipeline import ToolPipeline
from ar_testing.demo import demo_store

if TYPE_CHECKING:
    from typing import Any


def _props(schema: dict[str, object]) -> dict[str, object]:
    value = schema.get("properties")
    return value if isinstance(value, dict) else {}


def _required(schema: dict[str, object]) -> list[str]:
    value = schema.get("required")
    return [str(name) for name in value] if isinstance(value, list) else []


# Outcome buckets, most-to-least healthy.
WORKING = "working"
APPROVAL = "approval-gated"
POLICY = "policy-gated"
NEEDS_CONFIG = "needs-config"
NEEDS_REFERENT = "needs-referent"
FIXTURE = "fixture"
FAILING = "failing"

# Error codes that are a tool working correctly, not a defect: it is refusing because the
# install, a connection, a referent, the egress list or policy has not been set up.
_CONFIG_CODES = {
    "connector_not_installed",
    "not_installed",
    "not_connected",
    "unconfigured",
    "not_entitled",
    "not_allowlisted",
    "egress_denied",
    "sql_rejected",
    "quota_exceeded",
    "sandbox_unavailable",
    "browser_unavailable",
    "model_unconfigured",
    "no_model",
}
_REFERENT_CODES = {"not_found", "validation_failed"}
_POLICY_CODES = {"policy_denied", "approval_required", "awaiting_approval"}

_CONFIG_HINTS = (
    "not configured",
    "no model",
    "not connected",
    "unconfigured",
    "needs credentials",
    "credential",
    "not installed",
    "no connection",
    "embedding",
    "provider",
    "is not available",
    "disabled",
    "quota",
    "browser",
    "computer is not ready",
    "sandbox",
)
_REFERENT_HINTS = ("not found", "not_found", "does not exist", "no such")


def _referents(store: Any) -> dict[str, object]:
    """Collect real ids from the seeded demo tenant to fill referent-shaped arguments."""
    files = list(store.files.keys())
    conversations = list(store.conversations.keys())
    collections = list(getattr(store, "knowledge_collections", {}).keys())
    documents = list(getattr(store, "knowledge_documents", {}).keys())
    return {
        "file_id": str(files[0]) if files else str(uuid.uuid4()),
        "bytes_file_id": str(files[0]) if files else str(uuid.uuid4()),
        "conversation_id": str(conversations[0]) if conversations else str(uuid.uuid4()),
        "collection_id": str(collections[0]) if collections else str(uuid.uuid4()),
        "document_id": str(documents[0]) if documents else str(uuid.uuid4()),
    }


def _string_value(  # noqa: PLR0911 - a value generator is a chain of name heuristics
    name: str, prop: dict[str, object], referents: dict[str, object]
) -> object:
    lower = name.lower()
    if name in referents:
        return referents[name]
    enum = prop.get("enum")
    if isinstance(enum, list) and enum:
        return enum[0]
    for key in ("example", "default"):
        if prop.get(key) is not None:
            return prop[key]
    if "url" in lower:
        return "https://example.com"
    if "path" in lower:
        return "/workspace/matrix.txt"
    if "query" in lower or "sql" in lower:
        return "SELECT 1" if "sql" in lower else "test"
    if "command" in lower:
        return "echo matrix"
    if "code" in lower or "expression" in lower or "source" in lower or "script" in lower:
        return "print('matrix')"
    if "text" in lower or "content" in lower or "message" in lower:
        return "matrix probe text"
    if "name" in lower or "title" in lower:
        return "matrix"
    if lower.endswith("_id") or lower == "id":
        return str(uuid.uuid4())
    return "matrix"


def _value(name: str, prop: dict[str, object], referents: dict[str, object]) -> object:
    kind = prop.get("type")
    if isinstance(kind, list):
        kind = next((k for k in kind if k != "null"), "string")
    if kind == "object":
        return _args(prop, referents, required_only=True)
    if kind == "array":
        items = prop.get("items")
        if isinstance(items, dict):
            return [_value(name, items, referents)]
        return []
    if kind in {"integer", "number"}:
        enum = prop.get("enum")
        return enum[0] if isinstance(enum, list) and enum else 1
    if kind == "boolean":
        return False
    return _string_value(name, prop, referents)


def _args(
    schema: dict[str, object], referents: dict[str, object], *, required_only: bool
) -> dict[str, object]:
    props = _props(schema)
    required = _required(schema)
    out: dict[str, object] = {}
    for name, prop in props.items():
        if required_only and name not in required:
            continue
        if isinstance(prop, dict):
            out[str(name)] = _value(str(name), prop, referents)
    # A required field the schema never defined in ``properties`` (a catalogue defect):
    # still generate a value by name so the tool can be exercised past validation.
    for name in required:
        if str(name) not in out:
            out[str(name)] = _string_value(str(name), {}, referents)
    return out


def _schema_defect(schema: dict[str, object]) -> str:
    """A required field missing from ``properties`` means the tool's contract is broken."""
    props = _props(schema)
    missing = [name for name in _required(schema) if name not in props]
    return f"required but undefined in properties: {', '.join(missing)}" if missing else ""


def _classify(result: dict[str, object]) -> tuple[str, str]:  # noqa: PLR0911 - bucket guards
    status = str(result.get("status") or "")
    if status == "awaiting_approval":
        return APPROVAL, "write requires approval (gated, healthy)"
    error = result.get("error")
    if isinstance(error, dict):
        code = str(error.get("code") or "")
        message = str(error.get("message") or "")
        detail = f"{code}: {message[:120]}"
        if code in _POLICY_CODES:
            return POLICY, detail
        if code in _CONFIG_CODES or any(h in message.lower() for h in _CONFIG_HINTS):
            return NEEDS_CONFIG, detail
        if code in _REFERENT_CODES or any(h in message.lower() for h in _REFERENT_HINTS):
            return NEEDS_REFERENT, detail
        return FAILING, detail
    # A successful call.
    body = result.get("result")
    text = str(body)
    if "engine" in text and "fixture" in text:
        return FIXTURE, "returns a fixture result"
    return WORKING, status or "ok"


def _request(version: dict[str, object], arguments: dict[str, object]) -> dict[str, object]:
    return {
        "tenant_id": demo_id("tenant"),
        "user_id": demo_id("admin"),
        "synthetic": True,
        "tool_version_id": version["id"],
        "arguments": arguments,
        "model_call_id": f"matrix-{version.get('name')}",
    }


def run() -> int:
    store = demo_store()
    referents = _referents(store)
    pipeline = ToolPipeline(store)
    versions = sorted(
        store.tool_versions.values(), key=lambda row: str(row.get("qualified_name") or "")
    )
    rows: list[tuple[str, str, str, str, str]] = []
    for version in versions:
        qualified = str(version.get("qualified_name") or "")
        schema = (
            version.get("input_schema") if isinstance(version.get("input_schema"), dict) else {}
        )
        defect = _schema_defect(schema)
        arguments = _args(schema, referents, required_only=False)
        try:
            result = pipeline.execute(_request(version, arguments))
            bucket, note = _classify(result)
        except Exception as exc:  # noqa: BLE001 - a crash is the worst outcome, recorded
            bucket, note = FAILING, f"raised {type(exc).__name__}: {exc}"[:140]
        server = qualified.split(".", 1)[0]
        rows.append((server, qualified, bucket, note, defect))
    _report(rows)
    return 0


def _report(rows: list[tuple[str, str, str, str, str]]) -> None:
    counts = Counter(bucket for _, _, bucket, _, _ in rows)
    defects = [(q, d) for _, q, _, _, d in rows if d]
    out = Path("docs/testing/tool-matrix/report.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    live = "on" if os.environ.get("AR_TOOL_MATRIX_LIVE") else "off (fixtures, no model)"
    lines = [
        "# Tool working-state matrix",
        "",
        f"Generated by `scripts/tool_matrix.py`. Live model: **{live}**. "
        f"Every tool invoked through `ToolPipeline.execute` from the seeded demo tenant.",
        "",
        "## Summary",
        "",
        f"- Total tools: **{len(rows)}**",
    ]
    lines.extend(
        f"- {bucket}: **{counts.get(bucket, 0)}**"
        for bucket in (WORKING, APPROVAL, POLICY, NEEDS_CONFIG, NEEDS_REFERENT, FIXTURE, FAILING)
    )
    lines.append(f"- schema defects (required field undefined in properties): **{len(defects)}**")
    if defects:
        lines.extend(["", "## Schema defects", "", "| tool | defect |", "|---|---|"])
        lines.extend(f"| `{q}` | {d} |" for q, d in defects)
    current = ""
    for server, qualified, bucket, note, defect in rows:
        if server != current:
            current = server
            lines.extend(
                ["", f"## {server}", "", "| tool | state | note | schema |", "|---|---|---|---|"]
            )
        lines.append(f"| `{qualified}` | {bucket} | {note} | {'DEFECT' if defect else 'ok'} |")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"tool matrix: {len(rows)} tools -> {dict(counts)}")
    print(f"schema defects: {len(defects)}")
    print(f"report: {out}")
    if counts.get(FAILING):
        print(f"FAILING: {counts[FAILING]} tool(s) need attention", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(run())

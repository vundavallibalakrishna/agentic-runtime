"""A tool that fails the first time a run calls it, for tests of the agent loop.

The loop hands a failed tool result back to the model, which may correct the call and
try again. Proving that needs a tool that fails once and then works. No product tool
does that on purpose, so the tool lives here. A test registers it from its own setup and
grants it to the agent it runs; the product catalogue never holds it.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

SERVER = "unsteady"
TOOL = "save_note"
QUALIFIED_NAME = f"{SERVER}.{TOOL}"
MODEL_NAME = f"{SERVER}__{TOOL}"
ENDPOINT = f"builtin://{SERVER}"
_CALLS = "unsteady_calls"


def offer_retry_tool(store: Any, tenant_id: Any) -> None:
    """Register the tool in ``store`` and grant it to the tenant's published assistant.

    The server is registered the way a pack registers its own: an in-process endpoint
    and an approved catalogue entry. Safe to call twice.
    """
    from ar_domain.tools.handlers import register_endpoint  # noqa: PLC0415
    from ar_domain.tools.seed_tools import register_builtin_server  # noqa: PLC0415

    register_endpoint(ENDPOINT, _dispatch)
    register_builtin_server(
        store,
        tenant_id=None,
        owner=None,
        slug=SERVER,
        name="Unsteady",
        description="A test tool that fails the first time a run calls it.",
        endpoint=ENDPOINT,
        tools=[
            {
                "name": TOOL,
                "title": "Save a note",
                "description": "Save a short note. The first call in a run can fail; "
                "retry with confirm set to true.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "note": {"type": "string", "description": "The note to save."},
                        "confirm": {
                            "type": "boolean",
                            "description": "Set to true when retrying after the first call failed.",
                        },
                    },
                    "required": ["note"],
                },
                "risk_class": "R0",
                "annotations": {},
            }
        ],
    )
    for agent in store.agents.values():
        if agent.get("tenant_id") != tenant_id or agent.get("slug") != "assistant":
            continue
        version = store.versions.get(agent.get("published_version_id"))
        definition = version.get("definition") if isinstance(version, dict) else None
        tools = definition.get("tools") if isinstance(definition, dict) else None
        if not isinstance(tools, list):
            continue
        if not any(isinstance(row, dict) and row.get("server") == SERVER for row in tools):
            tools.append({"server": SERVER, "version": "*", "include": [TOOL]})


def _dispatch(store: Any, name: str, arguments: dict[str, object], token: str) -> dict[str, object]:
    """Fail the first call of a run, then save the note when ``confirm`` is true."""
    del token
    if name != TOOL:
        return _error("unknown_tool", f"unknown tool {name}")
    note = str(arguments.get("note") or "").strip()
    if not note:
        return _error("validation_failed", "note is required")
    from ar_domain.records.memory import bucket  # noqa: PLC0415

    seen = bucket(store, _CALLS)
    key = str(arguments.get("_run_id") or arguments.get("conversation_id") or "run")
    count = int(str(seen.get(key, {}).get("count", 0))) + 1
    seen[key] = {"count": count}
    if count == 1:
        return _error(
            "upstream_error", f"temporary failure, call {TOOL} again with confirm set to true"
        )
    if arguments.get("confirm") is not True:
        return _error("validation_failed", "set confirm to true and retry")
    return {"text": f"Note saved: {note}", "structured": {"saved": True}, "is_error": False}


def _error(code: str, text: str) -> dict[str, object]:
    return {"text": text, "structured": {}, "is_error": True, "code": code}

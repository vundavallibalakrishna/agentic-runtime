"""A tool that needs approval before it runs, for tests of the approval gate.

A write of risk class W2 stops at the policy gate until a person approves it. Proving
that needs a write that is safe to make and has nothing else to it. No product tool is
that on purpose, so the tool lives here, registered the way a pack registers its own: an
in-process endpoint and an approved catalogue entry. The product catalogue never holds it.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

SERVER = "proposals"
TOOL = "propose_change"
QUALIFIED_NAME = f"{SERVER}.{TOOL}"
MODEL_NAME = f"{SERVER}__{TOOL}"
ENDPOINT = f"builtin://{SERVER}"
BINDING: dict[str, object] = {"server": SERVER, "version": "*", "include": [TOOL]}


def offer_approval_tool(store: Any) -> None:
    """Register the tool in ``store``. Safe to call twice."""
    from ar_domain.tools.handlers import register_endpoint  # noqa: PLC0415
    from ar_domain.tools.seed_tools import register_builtin_server  # noqa: PLC0415

    register_endpoint(ENDPOINT, _dispatch)
    register_builtin_server(
        store,
        tenant_id=None,
        owner=None,
        slug=SERVER,
        name="Proposals",
        description="A test tool whose one write waits for approval.",
        endpoint=ENDPOINT,
        tools=[
            {
                "name": TOOL,
                "title": "Propose a change",
                "description": "Record a change to stored data. This waits for approval "
                "before it is saved.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "summary": {
                            "type": "string",
                            "description": "A short description of the change to be approved.",
                        }
                    },
                    "required": ["summary"],
                },
                "risk_class": "W2",
                "annotations": {},
            }
        ],
    )


def _dispatch(store: Any, name: str, arguments: dict[str, object], token: str) -> dict[str, object]:
    """Save the change. The policy gate runs this only after approval."""
    del store, token
    if name != TOOL:
        return _error("unknown_tool", f"unknown tool {name}")
    if not str(arguments.get("summary") or "").strip():
        return _error("validation_failed", "summary is required")
    return {"text": "Change saved.", "structured": {"saved": True}, "is_error": False}


def _error(code: str, text: str) -> dict[str, object]:
    return {"text": text, "structured": {}, "is_error": True, "code": code}

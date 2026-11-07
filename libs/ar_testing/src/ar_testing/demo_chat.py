"""The browser tests' chat scenarios for the stand-in model (M38a-T03).

The demo tenant's ``reasoning`` alias points at the stand-in, which answers the browser
specs' turns from this script set: a scenario for each answer and tool flow a spec expects.
A turn that matches nothing falls through to the stand-in's own default (an echo and the
``/tool <name> <json>`` command), so a spec that reads a plain answer still exercises a
real model call.

Each tool flow is two rules. The first ends the turn once the tool has run — it is guarded
on that tool's name (``last_tool_result.tool``), which the agent loop carries as the
``server__tool`` model name — so it never fires before the tool and never re-fires the
trigger. The second asks for the tool call. The answer rules come first because the first
matching script wins.
"""

from __future__ import annotations

from ar_domain.sandboxes.runtime import chart_command

DEMO_CHAT_SET = "demo-chat"

# A tool name as the agent loop sends it to the model: the qualified name with "." -> "__".
_TICKET = "tickets__create_ticket"
_ORDERS = "warehouse__run_query"
_CREATE_PET = "petstore__create_pet"
_DELETE_PET = "petstore__delete_pet"
_CHART = "sandbox__exec"


def _answer(trigger: str, tool: str, text: str) -> dict[str, object]:
    """End the turn after ``tool`` has run on a ``trigger`` message."""
    return {
        "match": {"contains": trigger, "last_tool_result": {"tool": tool}},
        "respond": {"text": text},
    }


def _call(trigger: str, tool: str, arguments: dict[str, object]) -> dict[str, object]:
    """Ask for one tool call when the message contains ``trigger``."""
    return {
        "match": {"contains": trigger},
        "respond": {"tool_calls": [{"name": tool, "arguments": arguments}]},
    }


DEMO_CHAT: list[dict[str, object]] = [
    # A `/tool <name> {json}` command: the stand-in's own default issues the call. Once it
    # has run, end the turn here so the default does not re-issue it every round.
    {
        "match": {"regex": "^/tool ", "last_tool_result": {}},
        "respond": {"text": "The tool ran."},
    },
    # A deliberately slow answer, so the chat shows its Stop control before the turn ends.
    {
        "match": {"contains": "answer slowly"},
        "respond": {"text": "I am answering slowly, one step at a time.", "delay_ms": 3000},
    },
    # Answers that end each tool flow (guarded on the tool, so they never re-trigger).
    _answer("File a ticket", _TICKET, "I filed that ticket for you."),
    _answer("orders are in the warehouse", _ORDERS, "I counted the orders in the warehouse."),
    _answer("Create a pet", _CREATE_PET, "The pet is created."),
    _answer("Delete pet", _DELETE_PET, "The pet is deleted."),
    _answer("chart revenue by month", _CHART, "Here is the revenue chart you asked for."),
    # The desk agent's and analyst's tool calls.
    _call("File a ticket", _TICKET, {"title": "Printer on floor 3 is jammed"}),
    _call("orders are in the warehouse", _ORDERS, {"sql": "SELECT count(*) FROM public.orders"}),
    _call("Create a pet", _CREATE_PET, {"body": {"name": "Fido"}}),
    _call("Delete pet", _DELETE_PET, {"petId": 1}),
    _call(
        "chart revenue by month",
        _CHART,
        {"command": chart_command(), "cwd": "/workspace", "timeout_s": 60},
    ),
    # When a recalled memory asks for bullet points, the model answers in bullet points.
    {
        "match": {"system_contains": "bullet points"},
        "respond": {"text": "- I kept this in bullet points because you asked me to."},
    },
]

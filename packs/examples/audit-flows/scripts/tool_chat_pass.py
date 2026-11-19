"""Ask for each tool's job in plain words and record whether the agent used that tool.

``scripts/tool_certification.py --only tools`` calls every tool directly. This is the
other half: one chat turn per tool, worded the way a person would ask and never naming
the tool, sent to an agent that is granted every tool listed here. A row passes when the
turn called the expected tool and the call succeeded. Nothing grades the wording of the
answer; a person reads ``tool-chat-pass.json``.

    AR_API_URL=http://127.0.0.1:18010 AR_ADMIN_EMAIL=... AR_ADMIN_PASSWORD=... \\
        uv run --no-sync python packs/examples/audit-flows/scripts/tool_chat_pass.py [tool ...]
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import orjson

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "scripts"))

import tool_certification as tc  # noqa: E402 - the signed-in client and chat helper live there

AUDIT = HERE.parent / "fixtures"
GRC = REPO / "packs" / "examples" / "grc-flows" / "fixtures"
OUT = Path(os.environ.get("AR_TOOL_CHAT_OUT", HERE.parent / "tool-chat-pass.json"))

ROWS = AUDIT / "sample-transactions.csv"
NOTES = AUDIT / "fieldwork-notes.md"
REPORT = AUDIT / "draft-audit-report.md"
POLICY = GRC / "acme-information-security-policy-v1.md"
POLICY_2 = GRC / "acme-information-security-policy-v2.md"
CONTROLS = GRC / "soc2-cc-subset.csv"
EXCERPT = GRC / "acme-soc2-report-excerpt.md"
NOTE = (
    "Access review note. Priya Raman (priya.raman@acme.example) still has administrator "
    "access to the payments console. Ticket SEC-2291."
)

# tool, what a person would say, files to attach
ASKS: list[tuple[str, str, list[Path]]] = [
    ("documents.compare", "What changed between these two versions?", [POLICY, POLICY_2]),
    ("documents.create", "Write a one-paragraph welcome note as a Word document.", []),
    ("documents.crosscheck", "Does this report contradict itself anywhere?", [REPORT]),
    ("documents.extract", "Pull out the auditor, the opinion and the period.", [EXCERPT]),
    ("documents.ingest", "Add this file to the document library.", [NOTES]),
    ("documents.judge", "Check the policy against each control in the list.", [POLICY, CONTROLS]),
    ("documents.list", "Which documents are in the library?", []),
    (
        "documents.missing",
        "Which of these does the policy leave out: a clean desk rule, a rule on personal "
        "devices, a rule on encryption in transit?",
        [POLICY],
    ),
    ("documents.outline", "Give me the section outline of this policy.", [POLICY]),
    ("documents.read", "Quote the access control section of this policy word for word.", [POLICY]),
    ("documents.redact", "Hide the personal data in this note.", []),
    (
        "documents.rewrite",
        "Propose a rewrite of the opening of this policy in plainer words.",
        [POLICY],
    ),
    ("documents.search", "Find where the library documents talk about log retention.", [POLICY]),
    ("documents.summarise", "Summarise this policy in five points.", [POLICY]),
    ("documents.tables", "Show me the tables in this document.", [REPORT]),
    ("general.chart", "Chart the number of transactions by channel.", [ROWS]),
    ("general.code", "Work out the 30th Fibonacci number by running code.", []),
    ("general.write_file", "Write a file called hello.txt containing the word hello.", []),
    (
        "general.edit_file",
        "Make a file called notes.txt that says alpha beta, then change beta to gamma in it.",
        [],
    ),
    ("general.move", "Make a file called a.txt containing x, then rename it to b.txt.", []),
    ("general.delete", "Make a file called scratch.txt containing hi, then delete it.", []),
    ("general.export_table", "Export the transactions over 50000 as an Excel file.", [ROWS]),
    ("general.glob", "Which CSV files are in my working folder?", [ROWS]),
    ("general.grep", "Find the lines that mention signature in the files I gave you.", [NOTES]),
    ("general.inspect_table", "What columns does this file have, and how many rows?", [ROWS]),
    ("general.list_files", "List the files in my working folder.", [ROWS]),
    ("general.pivot_table", "Give me total amount by channel across users, as a pivot.", [ROWS]),
    ("general.query_table", "How many transactions are over 20000?", [ROWS]),
    ("general.read_file", "Show me the first five lines of this file exactly.", [NOTES]),
    ("general.sample_table", "Draw a random sample of 10 rows from this file.", [ROWS]),
    (
        "general.save_query",
        "Save a query called big-ones that selects the transactions over 50000.",
        [ROWS],
    ),
    ("general.list_saved_queries", "Which saved queries do we have?", []),
    ("general.run_saved_query", "Run the saved query big-ones on this file.", [ROWS]),
    ("general.shell", "Run a shell command that prints today's date.", []),
    ("general.fetch", "Fetch https://example.com and tell me the page title.", []),
    ("general.http", "Send a GET request to https://example.com and tell me the status.", []),
    ("web.fetch", "Open https://example.com and tell me what the page says.", []),
    ("knowledge.list_collections", "Which knowledge collections can I use?", []),
    ("knowledge.search", "What does our knowledge library say about log retention?", []),
    ("memory.save", "Remember that my team's review day is Thursday.", []),
    ("memory.search", "What do you remember about my team's review day?", []),
    ("memory.forget", "Forget what you remember about my team's review day.", []),
    ("session.plan_update", "Plan in three steps how to review a policy, then begin.", []),
    ("files.list", "Which files have I uploaded?", [NOTES]),
    ("routines.list", "Which routines exist?", []),
    (
        "routines.create",
        "Create a routine that runs every Monday at 9 and lists the library documents.",
        [],
    ),
    ("conversations.search_history", "Search my earlier conversations for the word policy.", []),
]

SERVERS = (
    "documents",
    "general",
    "knowledge",
    "memory",
    "session",
    "files",
    "routines",
    "conversations",
    "web",
)


def make_agent(stack: tc.Stack) -> str:
    """An agent granted every tool this pass asks for, and the library to search."""
    slug = f"tool-pass-{int(time.time())}"
    stack.post("/api/v1/knowledge/collections", slug=slug, name="Tool pass library")
    listed = stack.get("/api/v1/knowledge/collections", limit=200)
    rows = listed.get("items") if isinstance(listed, dict) else []
    collection = next(str(row["id"]) for row in rows if row.get("slug") == slug)
    stack.post(
        f"/api/v1/knowledge/collections/{collection}/members",
        kind="text",
        title="Information security policy",
        text=POLICY_2.read_text(),
    )
    _s, agent = stack.post("/api/v1/agents", slug=slug, name="Tool pass", template="blank")
    agent_id = str(agent.get("id") or "") if isinstance(agent, dict) else ""
    if not agent_id:
        raise SystemExit(f"the agent was not created: {agent}")
    stack.remember("agent", agent_id)
    offered = {name.split(".", 1)[0] for name in stack.tools}
    stack.put(
        f"/api/v1/agents/{agent_id}/versions/draft",
        definition={
            "instructions": "Do what is asked with the tools you have, and say what you did.",
            "tools": [
                {"server": server, "include": ["*"]} for server in SERVERS if server in offered
            ],
            "knowledge": {"collections": [slug]},
        },
        changeNote="tool chat pass",
    )
    status, body = stack.post(f"/api/v1/agents/{agent_id}:publish", changeNote="tool chat pass")
    if status >= 300:
        raise SystemExit(f"the agent was not published: {body}")
    return agent_id


def main() -> None:
    stack = tc.Stack(
        os.environ.get("AR_API_URL", "http://127.0.0.1:18010"),
        os.environ.get("AR_ADMIN_EMAIL", ""),
        os.environ.get("AR_ADMIN_PASSWORD", ""),
    )
    wanted = set(sys.argv[1:])
    chat = tc.Chat(stack, make_agent(stack))
    kept: dict[str, object] = {}
    for tool, text, paths in ASKS:
        if wanted and tool not in wanted:
            continue
        if tool not in stack.tools:
            kept[tool] = {"outcome": "not in this catalogue"}
            continue
        conversation = chat.open()
        files = [
            chat.attach(
                path.name,
                path.read_bytes(),
                "text/csv" if path.suffix == ".csv" else "text/markdown",
            )
            for path in paths
        ]
        if tool == "documents.redact":
            files = [chat.attach("note.txt", NOTE.encode(), "text/plain")]
        started = time.monotonic()
        turn = chat.send(conversation, text, files or None)
        called = [f"{row.get('qualifiedName')}:{row.get('status')}" for row in turn.calls]
        if turn.called(tool):
            outcome = "used and succeeded"
        elif turn.tried(tool):
            outcome = "used, did not succeed"
        elif turn.status != "completed":
            outcome = f"turn {turn.status}"
        else:
            outcome = "not used"
        kept[tool] = {
            "asked": text,
            "outcome": outcome,
            "status": turn.status,
            "seconds": round(time.monotonic() - started, 1),
            "tools": called,
            "conversation": conversation,
            "answer": turn.text[:600],
        }
        print(f"{tool}: {outcome} ({kept[tool]['seconds']}s)", flush=True)  # type: ignore[index]
        OUT.write_bytes(orjson.dumps(kept, option=orjson.OPT_INDENT_2))
    stack.put_away()


if __name__ == "__main__":
    main()

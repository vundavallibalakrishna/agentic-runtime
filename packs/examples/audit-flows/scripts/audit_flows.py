"""Ask a running stack the questions a risk, audit or compliance team asks, and keep the answers.

Each scenario is one conversation, sent the way the chat screen sends it: files are
uploaded and attached, the agent chooses its own tools, and the reply, the tool calls and
the conversation id are written to ``evidence.json``. The prompts name no tool. Nothing
here grades an answer: a person reads the evidence, in the file and on the chat screen.

Run against a stack with a real model on the ``reasoning`` and ``embed`` aliases:

    AR_API_URL=http://127.0.0.1:18010 AR_ADMIN_EMAIL=... AR_ADMIN_PASSWORD=... \\
        uv run --no-sync python packs/examples/audit-flows/scripts/audit_flows.py [scenario ...]
"""

from __future__ import annotations

import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

import orjson

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "scripts"))

import tool_certification as tc  # noqa: E402 - the signed-in client and chat helper live there

AUDIT = HERE.parent / "fixtures"
GRC = REPO / "packs" / "examples" / "grc-flows" / "fixtures"
EVIDENCE = Path(os.environ.get("AR_AUDIT_EVIDENCE", HERE.parent / "evidence.json"))

STAFF_NOTE = (
    "Access review note. Priya Raman (priya.raman@acme.example, +1 415 555 0134) still has "
    "administrator access to the payments console after moving to the finance team on "
    "3 March 2026. Her manager, Tom Okafor, asked for it to be removed. Ticket SEC-2291."
)
PAST_PROGRAMME = (
    "Audit programme used in the 2025 account opening review. "
    "Step 1: obtain the list of accounts opened in the period and agree the count to the "
    "system report. Step 2: for a sample, inspect the application for the manager signature "
    "before activation. Step 3: for the same sample, confirm a transaction profile was "
    "recorded before activation. Step 4: obtain the monthly reports of accounts over profile "
    "and confirm each review was recorded. Step 5: reperform the over-profile report from "
    "transaction data for one month and compare it with the report reviewed."
)
ROUGH_PARAGRAPH = (
    "We seen that 4 accounts out of the 25 was activated and the manager did not sign, which "
    "is not as per the procedure para 2.2, this happen because of month end and staff were "
    "less, also system is not stopping it."
)


@dataclass
class Scenario:
    key: str
    need: str
    turns: list[str]
    files: list[Path] = field(default_factory=list)
    later_files: dict[int, list[Path]] = field(default_factory=dict)
    agent: str = "assistant"


SCENARIOS = [
    Scenario(
        "G1-gap",
        "Gap analysis of a policy against a control list",
        [
            "Check this policy against each control in the attached control list. For each "
            "control say whether the policy meets it, partly meets it or says nothing, and "
            "quote the policy's words.",
            "Write that up as a one-page memo for the security committee, as a Word document.",
            "Give me the same table as an Excel file and the memo as a PDF too.",
        ],
        [GRC / "acme-information-security-policy-v1.md", GRC / "soc2-cc-subset.csv"],
    ),
    Scenario(
        "G2-compare",
        "What changed between two versions",
        ["What changed between these two versions of the policy? List each change."],
        [
            GRC / "acme-information-security-policy-v1.md",
            GRC / "acme-information-security-policy-v2.md",
        ],
    ),
    Scenario(
        "G3-contract",
        "Contract review against a standard, then a clause rewrite",
        [
            "Review the vendor's draft against our standard agreement. What is missing or "
            "worse for us?",
            "Propose a rewrite of the breach notification clause in the vendor draft so it "
            "says 48 hours.",
        ],
        [GRC / "acme-dpa-standard.md", GRC / "vendor-dpa-draft.md"],
    ),
    Scenario(
        "G4-extract",
        "Pull facts from a report and summarise it with section references",
        [
            "Who is the auditor, what opinion did they give, and what period does the report "
            "cover?",
            "Summarise the report in five points and say which section each point comes from.",
        ],
        [GRC / "acme-soc2-report-excerpt.md"],
    ),
    Scenario(
        "G5-redact",
        "Hide personal data",
        ["Hide the personal data in this note and give me the clean version."],
        [],
    ),
    Scenario(
        "G7-charts",
        "Tables, pivots and charts from a data file",
        [
            "Chart the number of transactions by channel.",
            "Now a table of total amount by channel and month.",
            "Export that table as an Excel file.",
        ],
        [AUDIT / "sample-transactions.csv"],
    ),
    Scenario(
        "G8-deck",
        "A presentation from findings",
        [
            "Read these fieldwork notes and turn the findings into a five-slide presentation "
            "for the audit committee."
        ],
        [AUDIT / "fieldwork-notes.md"],
    ),
    Scenario(
        "G9-questionnaire",
        "Answer a questionnaire from the library, with sources",
        ["Answer each question in the attached questionnaire from our library. Give the source."],
        [GRC / "vendor-questionnaire.csv"],
        agent="analyst",
    ),
    Scenario(
        "AAT103a-draft",
        "Draft an observation from rough notes and test results",
        [
            "Draft the observation for test step T1 with these headings: condition, criteria, "
            "cause, effect, recommendation. Use only what is in the notes and the procedure, "
            "and after each statement cite the test step or the paragraph it comes from."
        ],
        [AUDIT / "fieldwork-notes.md", AUDIT / "account-opening-procedure-v1.md"],
    ),
    Scenario(
        "AAT103b-improve",
        "Improve a draft without changing its meaning",
        [
            "Improve the language and tone of this paragraph without changing its meaning or "
            f"adding any fact:\n\n{ROUGH_PARAGRAPH}"
        ],
    ),
    Scenario(
        "AAT103c-programme",
        "Suggest programme steps from the library and past work",
        [
            "Suggest audit programme steps for the transaction profile process, drawing on our "
            "library and previous engagements. Say where each step comes from."
        ],
        agent="analyst",
    ),
    Scenario(
        "AAT103d-summary",
        "Summarise a procedure and point to the relevant paragraphs",
        [
            "I am testing the transaction profile. Summarise this procedure and point me to "
            "the paragraphs relevant to my test."
        ],
        [AUDIT / "account-opening-procedure-v1.md"],
    ),
    Scenario(
        "AAT103e-executive",
        "Executive summary of an engagement's observations",
        ["Write an executive summary of the observations in these notes for the report."],
        [AUDIT / "fieldwork-notes.md"],
    ),
    Scenario(
        "AAT103f-consistency",
        "Find internal inconsistencies in a draft report",
        ["Check this draft report for internal inconsistencies."],
        [AUDIT / "draft-audit-report.md"],
    ),
    Scenario(
        "AAT104-rule",
        "Plain-language test to a proposed rule, a sample run, then approval and reuse",
        [
            "I want to list all accounts opened in the last quarter (July to September 2026) "
            "where the transaction profile was not obtained, or where actual transactions in "
            "any month exceed the declared monthly amount by more than 50 percent. First "
            "propose the rule: name the files and fields you will use and explain the logic "
            "in plain language. Do not run it yet.",
            "That is right. Run it on these sample files and show the output and the record count.",
            "Save this rule so I can reuse it next quarter. It must not run on production "
            "data until my head of unit has approved it.",
        ],
        [AUDIT / "sample-accounts.csv", AUDIT / "sample-transactions.csv"],
    ),
    Scenario(
        "AAT105-matrix",
        "Processes, risks and controls from a procedure, with references, then a revision",
        [
            "Build a risk and control matrix from this procedure with these columns: process, "
            "sub-process, risk, control, control type (preventive or detective, manual or "
            "automated), control owner, frequency, and the paragraph each line comes from. "
            "Where the document states a risk but no control, flag the gap. Do not invent a "
            "control.",
            "Give me the matrix as an Excel file.",
            "The procedure has been revised, the new version is attached. What changes "
            "against the matrix? Do not rebuild it, show only the differences.",
        ],
        [AUDIT / "account-opening-procedure-v1.md"],
        later_files={2: [AUDIT / "account-opening-procedure-v2.md"]},
    ),
    Scenario(
        "AAT059-sampling",
        "Random, stratified and monetary-unit samples, reproducible and documented",
        [
            "Select a random sample of 25 transactions from this file. It must be "
            "reproducible. Document the method, the parameters and the population.",
            "Now a stratified sample: 5 transactions from each channel.",
            "Now a monetary unit sample of 20 items.",
            "Add TX-00010 and TX-00020 to the last sample as judgmental items, because they "
            "were raised by the branch manager. Flag them as judgmental with that reason.",
        ],
        [AUDIT / "sample-transactions.csv"],
    ),
    Scenario(
        "AAT060-filter",
        "Combined filters and a free-form query, then save it for reuse",
        [
            "Show the transactions over 20000 that have a compliance flag. How many are there?",
            "Which three users posted the most transactions through the online channel, and "
            "how many each?",
            "Save the first filter as 'large flagged' so I can run it again next month on "
            "new data.",
        ],
        [AUDIT / "sample-transactions.csv"],
    ),
]


def make_analyst(stack: tc.Stack) -> str:
    """An agent with the document tools, the table tools and the library search."""
    slug = f"audit-analyst-{int(time.time())}"
    _s, made = stack.post("/api/v1/knowledge/collections", slug=slug, name="Audit library")
    collection = str(made.get("id") or "") if isinstance(made, dict) else ""
    members = {
        "Information security policy": (GRC / "acme-information-security-policy-v2.md").read_text(),
        "Assurance report excerpt": (GRC / "acme-soc2-report-excerpt.md").read_text(),
        "Account opening procedure": (AUDIT / "account-opening-procedure-v1.md").read_text(),
        "Account opening review 2025: audit programme": PAST_PROGRAMME,
    }
    for title, text in members.items():
        stack.post(
            f"/api/v1/knowledge/collections/{collection}/members",
            kind="text",
            title=title,
            text=text,
        )
    _s, agent = stack.post("/api/v1/agents", slug=slug, name="Audit analyst", template="blank")
    agent_id = str(agent.get("id") or "") if isinstance(agent, dict) else ""
    if not agent_id:
        raise SystemExit(f"the analyst agent was not created: {agent}")
    stack.put(
        f"/api/v1/agents/{agent_id}/versions/draft",
        definition={
            "instructions": (
                "You help a review team. Work only from the documents, the files and the "
                "library you are given, and say where each statement comes from. If the "
                "sources say nothing, say so. Never invent a fact, a figure or a reference."
            ),
            "tools": [
                {"server": "documents", "include": ["*"]},
                {"server": "knowledge", "include": ["search"]},
            ],
            # A definition names a collection by its slug.
            "knowledge": {"collections": [slug]},
        },
        changeNote="audit flows",
    )
    stack.post(f"/api/v1/agents/{agent_id}:publish", changeNote="audit flows")
    return agent_id


def run_one(stack: tc.Stack, agents: dict[str, str], scenario: Scenario) -> dict[str, object]:
    chat = tc.Chat(stack, agents[scenario.agent])
    conversation = chat.open()
    turns: list[dict[str, object]] = []
    for index, text in enumerate(scenario.turns):
        paths = scenario.files if index == 0 else scenario.later_files.get(index, [])
        files = [
            chat.attach(
                path.name,
                path.read_bytes(),
                "text/csv" if path.suffix == ".csv" else "text/markdown",
            )
            for path in paths
        ]
        if scenario.key == "G5-redact" and index == 0:
            files = [chat.attach("access-review-note.txt", STAFF_NOTE.encode(), "text/plain")]
        started = time.monotonic()
        turn = chat.send(conversation, text, files or None)
        turns.append(
            {
                "asked": text,
                "status": turn.status,
                "seconds": round(time.monotonic() - started, 1),
                "tools": [f"{row.get('qualifiedName')}:{row.get('status')}" for row in turn.calls],
                "parts": sorted({str(row.get("type")) for row in turn.parts}),
                "files": [
                    str(row.get("name") or row.get("filename") or "")
                    for row in turn.parts
                    if row.get("type") in {"file", "artifact"}
                ],
                "answer": turn.text,
            }
        )
        print(
            f"{scenario.key} turn {index + 1}: {turn.status} in {turns[-1]['seconds']}s", flush=True
        )
    return {
        "scenario": scenario.key,
        "need": scenario.need,
        "agent": scenario.agent,
        "conversation": conversation,
        "turns": turns,
    }


def main() -> None:
    stack = tc.Stack(
        os.environ.get("AR_API_URL", "http://127.0.0.1:18010"),
        os.environ.get("AR_ADMIN_EMAIL", ""),
        os.environ.get("AR_ADMIN_PASSWORD", ""),
    )
    wanted = set(sys.argv[1:])
    chosen = [row for row in SCENARIOS if not wanted or row.key in wanted]
    listed = stack.get("/api/v1/agents", limit=200)
    rows = listed.get("items") if isinstance(listed, dict) else []
    agents = {
        "assistant": next(str(row["id"]) for row in rows if row.get("slug") == "assistant"),
    }
    if any(row.agent == "analyst" for row in chosen):
        agents["analyst"] = make_analyst(stack)
    kept: dict[str, object] = orjson.loads(EVIDENCE.read_bytes()) if EVIDENCE.exists() else {}
    workers = int(os.environ.get("AR_AUDIT_WORKERS", "3"))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for result in pool.map(lambda row: run_one(stack, agents, row), chosen):
            kept[str(result["scenario"])] = result
            EVIDENCE.write_bytes(orjson.dumps(kept, option=orjson.OPT_INDENT_2))


if __name__ == "__main__":
    main()

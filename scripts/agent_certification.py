"""Check that agents can be built, published, configured and run, on a running stack.

    AR_API_URL=... AR_ADMIN_EMAIL=... AR_ADMIN_PASSWORD=... \\
        uv run python scripts/agent_certification.py [--stage build] [--case rollback]

Every case goes through the public API as a signed-in person, with the model the tenant
has registered. A case makes what it needs, checks an outcome a person could check, and
the agents it made are archived at the end. The verdicts are:

- ``pass``     the outcome was the expected one
- ``fail``     it was not; the note says what was seen
- ``blocked``  the install lacks something the case needs; the note says what

``AR_SECOND_EMAIL`` and ``AR_SECOND_PASSWORD`` name a second person of the tenant, for
the cases that need two. The evidence file lists the conversation of every case that had
one, so it can be opened in the product.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import orjson

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tool_certification import (
    CSV,
    POLICY,
    Chat,
    Stack,
    Turn,
    _approval_agent,
    _decide,
    _has_file,
    _request_for,
)

if TYPE_CHECKING:
    from collections.abc import Callable

Body = dict[str, object]
OK = 300


class Blocked(Exception):  # noqa: N818 — a verdict, not an error
    """The install lacks what the case needs."""


@dataclass
class Bench:
    """The signed-in sessions and what the cases have made so far."""

    stack: Stack
    second: Stack | None
    stamp: int = field(default_factory=lambda: int(time.time()))
    count: int = 0
    seen: list[str] = field(default_factory=list)

    def slug(self, name: str) -> str:
        self.count += 1
        return f"ac-{name}-{self.stamp}-{self.count}"

    def agent(self, name: str, definition: Body | None = None, **more: object) -> tuple[str, str]:
        """A published agent with this definition. Returns its id and slug."""
        slug = self.slug(name)
        agent = self.create(slug, **more)
        if definition is not None:
            self.draft(agent, definition)
        self.publish(agent)
        return agent, slug

    def create(self, slug: str, **more: object) -> str:
        body: Body = {"slug": slug, "name": slug, "template": "blank", **more}
        status, made = self.stack.post("/api/v1/agents", **body)
        if status >= OK or not isinstance(made, dict):
            raise AssertionError(f"the agent was not created ({status}): {_said(made)}")
        self.stack.remember("agent", str(made["id"]))
        return str(made["id"])

    def draft(self, agent: str, definition: Body, note: str = "certification") -> None:
        status, body = self.stack.put(
            f"/api/v1/agents/{agent}/versions/draft", definition=definition, changeNote=note
        )
        if status >= OK:
            raise AssertionError(f"the draft was not saved ({status}): {_said(body)}")

    def publish(self, agent: str, **more: object) -> Body:
        status, body = self.stack.post(
            f"/api/v1/agents/{agent}:publish", changeNote="certification", **more
        )
        if status >= OK:
            raise AssertionError(f"the agent was not published ({status}): {_said(body)}")
        return body if isinstance(body, dict) else {}

    def ask(
        self,
        agent: str,
        text: str,
        *,
        who: Stack | None = None,
        files: list[tuple[str, str, str]] | None = None,
        **extra: object,
    ) -> Turn:
        """One question in a new conversation. ``files`` are (name, text, media type)."""
        chat = Chat(who or self.stack, agent)
        conversation = chat.open()
        if not conversation:
            return Turn(status="no conversation")
        self.seen.append(conversation)
        attached = [chat.attach(name, body.encode(), mime) for name, body, mime in files or []]
        return chat.send(conversation, text, attached or None, **extra)

    def start(self, agent: str, text: str) -> tuple[str, str]:
        """Send one message and return at once, with the conversation and the run."""
        chat = Chat(self.stack, agent)
        conversation = chat.open()
        self.seen.append(conversation)
        status, posted = self.stack.post(
            f"/api/v1/conversations/{conversation}/messages", text=text
        )
        if status >= OK or not isinstance(posted, dict):
            raise AssertionError(f"the message was refused ({status}): {_said(posted)}")
        run = posted.get("run")
        return conversation, str(
            run.get("id") if isinstance(run, dict) else posted.get("runId") or ""
        )

    def run_status(self, run: str, *, until: set[str], wait_s: float = 240) -> str:
        deadline = time.monotonic() + wait_s
        status = ""
        while time.monotonic() < deadline:
            seen = self.stack.get(f"/api/v1/runs/{run}")
            status = str(seen.get("status") or "") if isinstance(seen, dict) else ""
            if status in until:
                return status
            time.sleep(2)
        return status or "unknown"

    def reply(self, conversation: str, run: str) -> str:
        """What the run itself answered, whatever else was written to the conversation."""
        seen = self.stack.get(f"/api/v1/conversations/{conversation}")
        messages = seen.get("messages") if isinstance(seen, dict) else []
        for row in messages if isinstance(messages, list) else []:
            if row.get("role") == "assistant" and str(row.get("runId")) == run:
                return str(row.get("text") or "")
        return ""

    def others(self, conversation: str, run: str) -> list[Body]:
        """Messages in the conversation that belong to some other run than the one asked."""
        seen = self.stack.get(f"/api/v1/conversations/{conversation}")
        messages = seen.get("messages") if isinstance(seen, dict) else []
        return [
            row
            for row in (messages if isinstance(messages, list) else [])
            if isinstance(row, dict) and str(row.get("runId")) != run
        ]

    def last(self, conversation: str) -> Turn:
        seen = self.stack.get(f"/api/v1/conversations/{conversation}")
        return Chat(self.stack, "")._last(seen) if isinstance(seen, dict) else Turn(status="gone")


def _said(body: object) -> str:
    if isinstance(body, dict):
        return str(body.get("detail") or body.get("code") or body)[:200]
    return str(body)[:200]


def _body(value: object) -> Body:
    """The value as a mapping. A case checks it is one before it reads it."""
    return value if isinstance(value, dict) else {}


def _rows(body: object) -> list[Body]:
    if isinstance(body, dict):
        found = body.get("items", body.get("data"))
        return [row for row in found if isinstance(row, dict)] if isinstance(found, list) else []
    return [row for row in body if isinstance(row, dict)] if isinstance(body, list) else []


def expect(condition: object, note: str) -> None:
    if not condition:
        raise AssertionError(note)


# --- Stage: build ------------------------------------------------------------------------


def case_templates(bench: Bench) -> str:
    """Each template makes an agent that can be published and answers a question."""
    notes = []
    for template in ("blank", "assistant", "researcher", "analyst", "support"):
        agent = bench.create(bench.slug(template), template=template)
        bench.publish(agent)
        turn = bench.ask(agent, "In one short sentence, what can you help me with?")
        expect(turn.status == "completed" and turn.text.strip(), f"{template}: {turn.status}")
        notes.append(template)
    return f"{len(notes)} templates published and answered"


def case_builder(bench: Bench) -> str:
    """An agent described in plain words is drafted, previewed, applied, published and run."""
    status, session = bench.stack.post(
        "/api/v1/builder/sessions",
        instruction="An agent that answers questions about office opening hours. It is "
        "polite, answers in one or two sentences, and says so when it does not know.",
    )
    expect(
        status < OK and isinstance(session, dict),
        f"no builder session ({status}): {_said(session)}",
    )
    session = _body(session)
    session_id = str(session.get("sessionId") or session.get("id") or "")
    expect(session_id, f"no session id: {list(session)[:12]}")
    proposal = _proposal(bench, session_id)
    expect(proposal, "the session never showed a proposal to review")
    status, changed = bench.stack.post(
        f"/api/v1/builder/sessions/{session_id}/messages",
        text="Also make it answer in British English.",
    )
    expect(status < OK, f"the follow-up was refused ({status}): {_said(changed)}")
    status, applied = bench.stack.post(
        f"/api/v1/builder/sessions/{session_id}:apply", mode="create"
    )
    expect(status < OK and isinstance(applied, dict), f"apply failed ({status}): {_said(applied)}")
    applied = _body(applied)
    agent = str(
        applied.get("agentId") or applied.get("id") or (applied.get("agent") or {}).get("id") or ""
    )
    expect(agent, f"apply returned no agent: {list(applied)[:12]}")
    bench.stack.remember("agent", agent)
    bench.publish(agent)
    turn = bench.ask(agent, "When are you open on Sundays? I have not told you your hours.")
    expect(turn.status == "completed", f"the built agent did not answer: {turn.status}")
    return f"built from words and answered: {turn.text[:80]!r}"


def _proposal(bench: Bench, session_id: str, wait_s: float = 120) -> object:
    """The reviewable draft of a builder session, once the builder has written it."""
    deadline = time.monotonic() + wait_s
    while time.monotonic() < deadline:
        seen = bench.stack.get(f"/api/v1/builder/sessions/{session_id}")
        if isinstance(seen, dict) and seen.get("proposal"):
            return seen["proposal"]
        time.sleep(2)
    return None


def case_edit_and_validate(bench: Bench) -> str:
    """A draft is edited and validated; a definition that is wrong is refused in words."""
    agent = bench.create(bench.slug("edit"))
    bench.draft(agent, {"instructions": "End every answer with the word DONE."})
    status, checked = bench.stack.post(f"/api/v1/agents/{agent}:validate")
    expect(status < OK, f"validate failed ({status}): {_said(checked)}")
    bench.publish(agent)
    turn = bench.ask(agent, "Say hello.")
    expect("DONE" in turn.text, f"the edited instructions were not followed: {turn.text[:120]}")
    status, refused = bench.stack.put(
        f"/api/v1/agents/{agent}/versions/draft",
        definition={"instructions": "x", "tools": [{"server": "no-such-server", "include": ["*"]}]},
        changeNote="bad",
    )
    if status < OK:
        status, refused = bench.stack.post(f"/api/v1/agents/{agent}:publish", changeNote="bad")
    expect(status >= 400, "a tool server that does not exist was accepted")
    expect("no-such-server" in str(refused) or "unknown" in str(refused).lower(), _said(refused))
    status, shaped = bench.stack.put(
        f"/api/v1/agents/{agent}/versions/draft",
        definition={"instructions": 7, "budget": {"max_steps": "many"}},
        changeNote="bad",
    )
    expect(status >= 400, "a definition of the wrong shape was accepted")
    return f"edited, validated, and two bad definitions refused: {_said(shaped)[:80]}"


def case_rollback(bench: Bench) -> str:
    """Rolling back to version 1 brings back what version 1 did."""
    agent = bench.create(bench.slug("rollback"))
    bench.draft(agent, {"instructions": "Answer every message with exactly the word ALPHA."})
    bench.publish(agent)
    bench.draft(agent, {"instructions": "Answer every message with exactly the word BETA."})
    bench.publish(agent)
    expect("BETA" in bench.ask(agent, "Go.").text.upper(), "version 2 is not what runs")
    status, body = bench.stack.post(
        f"/api/v1/agents/{agent}:rollback", version=1, changeNote="back"
    )
    expect(status < OK, f"rollback failed ({status}): {_said(body)}")
    text = bench.ask(agent, "Go.").text.upper()
    expect("ALPHA" in text and "BETA" not in text, f"after rollback it said: {text[:80]}")
    versions = _rows(bench.stack.get(f"/api/v1/agents/{agent}/versions"))
    return f"version 1 runs again; {len(versions)} versions are kept"


def case_bundle(bench: Bench) -> str:
    """An exported agent is imported under another name and runs."""
    agent, slug = bench.agent(
        "bundle", {"instructions": "Answer every message with the word GAMMA."}
    )
    exported = bench.stack.client.get(
        "/api/v1/bundles:export", params={"ids": agent}, headers={"accept": "application/json"}
    )
    expect(exported.status_code < OK, f"export failed ({exported.status_code})")
    document = exported.json()
    text = orjson.dumps(document).decode()
    copy = bench.slug("imported")
    expect(slug in text, "the export does not name the agent")
    status, checked = bench.stack.post(
        "/api/v1/bundles:import", bundle=orjson.loads(text.replace(slug, copy)), dryRun=True
    )
    expect(status < OK, f"the dry run failed ({status}): {_said(checked)}")
    status, made = bench.stack.post(
        "/api/v1/bundles:import", bundle=orjson.loads(text.replace(slug, copy))
    )
    expect(status < OK, f"import failed ({status}): {_said(made)}")
    found = next(
        (
            row
            for row in _rows(bench.stack.get("/api/v1/agents", limit=200))
            if row.get("slug") == copy
        ),
        None,
    )
    expect(found is not None, f"the imported agent is not listed: {_said(made)}")
    found = _body(found)
    imported = str(found["id"])
    bench.stack.remember("agent", imported)
    if found.get("status") != "published":
        bench.publish(imported)
    expect(
        "GAMMA" in bench.ask(imported, "Go.").text.upper(), "the imported agent answers differently"
    )
    return f"exported, imported as {copy}, and it answers the same"


def case_visibility(bench: Bench) -> str:
    """A private agent is the owner's alone; a tenant agent is everyone's."""
    if bench.second is None:
        raise Blocked("a second person (AR_SECOND_EMAIL, AR_SECOND_PASSWORD)")
    me = bench.second.get("/api/v1/me")
    roles = set(me.get("roles") or me.get("roleKeys") or []) if isinstance(me, dict) else set()
    private, private_slug = bench.agent(
        "private", {"instructions": "Say hi."}, visibility="private"
    )
    shared, shared_slug = bench.agent("shared", {"instructions": "Say hi."}, visibility="tenant")
    theirs = {str(row.get("slug")) for row in _rows(bench.second.get("/api/v1/agents", limit=200))}
    expect(shared_slug in theirs, "a tenant agent is not listed for a second person")
    one = bench.second.client.get(f"/api/v1/agents/{private}")
    if "tenant_admin" in roles:
        # An administrator may manage every agent, so the private one is theirs to see.
        expect(one.status_code < OK, "an administrator cannot open a private agent")
        raise Blocked(
            "a second person who is not an administrator: the tenant agent is seen by both, "
            "and the private one by its owner and by the administrator, as designed"
        )
    expect(private_slug not in theirs, "a private agent is listed for someone else")
    expect(one.status_code == 404, f"a private agent opens for someone else ({one.status_code})")
    turn = bench.ask(shared, "Hello", who=bench.second)
    expect(turn.status == "completed", f"a second person cannot run a tenant agent: {turn.status}")
    return "private is the owner's alone; tenant is seen and run by a second person"


def case_disable(bench: Bench) -> str:
    """A disabled agent takes no new work, says why, and works again when enabled."""
    agent, _slug = bench.agent("switch", {"instructions": "Say hi."})
    status, body = bench.stack.post(f"/api/v1/agents/{agent}:disable", reason="certification")
    expect(status < OK, f"disable failed ({status}): {_said(body)}")
    status, refused = bench.stack.post("/api/v1/conversations", agentId=agent)
    if status < OK and isinstance(refused, dict):
        status, refused = bench.stack.post(
            f"/api/v1/conversations/{refused['id']}/messages", text="Hello"
        )
    expect(status >= 400, "a disabled agent accepted a message")
    said = _said(refused)
    status, body = bench.stack.post(f"/api/v1/agents/{agent}:enable")
    expect(status < OK, f"enable failed ({status}): {_said(body)}")
    expect(bench.ask(agent, "Hello").status == "completed", "the enabled agent does not answer")
    status, body = bench.stack.post(f"/api/v1/agents/{agent}:archive")
    expect(status < OK, f"archive failed ({status}): {_said(body)}")
    listed = {str(row.get("id")) for row in _rows(bench.stack.get("/api/v1/agents", limit=200))}
    status, body = bench.stack.post(f"/api/v1/agents/{agent}:unarchive")
    expect(status < OK, f"unarchive failed ({status}): {_said(body)}")
    hidden = (
        "hidden from the list while archived"
        if agent not in listed
        else "still listed while archived"
    )
    return f"disabled refused with: {said[:70]!r}; enabled again; {hidden}"


def case_stale_edit(bench: Bench) -> str:
    """Two people edit from the same copy: the second save is refused, not silently kept."""
    agent = bench.create(bench.slug("stale"))
    first = bench.stack.get(f"/api/v1/agents/{agent}")
    tag = str(first.get("etag") or "") if isinstance(first, dict) else ""
    expect(tag, "the agent has no etag to edit against")
    one = bench.stack.client.patch(
        f"/api/v1/agents/{agent}", json={"description": "first"}, headers={"If-Match": tag}
    )
    expect(one.status_code < OK, f"the first edit failed ({one.status_code})")
    two = bench.stack.client.patch(
        f"/api/v1/agents/{agent}", json={"description": "second"}, headers={"If-Match": tag}
    )
    expect(two.status_code == 412, f"the stale edit got {two.status_code}, not 412")
    kept = bench.stack.get(f"/api/v1/agents/{agent}")
    expect(isinstance(kept, dict) and kept.get("description") == "first", "the stale edit was kept")
    return "the second save from an old copy was refused with 412"


# --- Stage: configure --------------------------------------------------------------------

_TABLE = [("regions.csv", CSV, "text/csv")]
_GENERAL = {"server": "general", "include": ["inspect_table", "query_table"]}
_DONE = {"completed", "failed", "cancelled", "budget_exceeded"}


def case_tools(bench: Bench) -> str:
    """An agent uses the tools it is given and cannot use one it is not given."""
    able, _ = bench.agent("tools", {"instructions": "Use your tools.", "tools": [_GENERAL]})
    question = "Use a query to add up the count column of the attached file. Give the total."
    turn = bench.ask(able, question, files=_TABLE)
    expect(turn.called("general.query_table"), f"the bound tool was not used ({turn.status})")
    expect("53" in turn.text, f"the total is wrong: {turn.text[:100]}")
    bare, _ = bench.agent("no-tools", {"instructions": "Answer as best you can.", "tools": []})
    plain = bench.ask(bare, question, files=_TABLE)
    used = [str(row.get("qualifiedName")) for row in plain.calls]
    expect(not any(name.startswith("general.") for name in used), f"an unbound tool ran: {used}")
    return f"bound tool used and total right; with no tools bound nothing ran ({plain.status})"


def case_knowledge(bench: Bench) -> str:
    """An agent answers from the collection it is bound to, and not without it."""
    slug = bench.slug("library")
    status, made = bench.stack.post("/api/v1/knowledge/collections", slug=slug, name=slug)
    if status >= OK or not isinstance(made, dict):
        raise Blocked(f"a knowledge collection ({_said(made)})")
    status, member = bench.stack.post(
        f"/api/v1/knowledge/collections/{made['id']}/members",
        kind="text",
        title="Access control policy",
        text=POLICY,
    )
    if status >= OK:
        raise Blocked(f"an embedding model on the embed alias ({_said(member)})")
    _wait_indexed(bench, str(made["id"]))
    reader, _ = bench.agent(
        "reader",
        {
            "instructions": "Answer from the organisation's knowledge. Cite what you used.",
            "knowledge": {"collections": [slug], "auto_retrieve": True},
            "tools": [{"server": "knowledge", "include": ["*"]}],
        },
    )
    question = "What is the reference code of the access control policy?"
    turn = bench.ask(reader, question)
    expect("ZEBRA-4417" in turn.text, f"the bound agent did not find it: {turn.text[:120]}")
    other, _ = bench.agent(
        "no-library", {"instructions": "Answer briefly. Say so if unsure.", "tools": []}
    )
    without = bench.ask(other, question)
    expect("ZEBRA-4417" not in without.text, "an agent with no knowledge tool knew the answer")
    return "found in the bound collection; an agent with no knowledge tool did not know"


def case_knowledge_confined(bench: Bench) -> str:
    """An agent bound to one collection does not answer from another one."""
    made: dict[str, str] = {}
    for name, text in (
        ("sales", "# Sales\n\nThe sales desk code word is HERON-2209.\n"),
        ("payroll", "# Payroll\n\nThe payroll desk code word is OTTER-7731.\n"),
    ):
        slug = bench.slug(name)
        status, row = bench.stack.post("/api/v1/knowledge/collections", slug=slug, name=slug)
        if status >= OK or not isinstance(row, dict):
            raise Blocked(f"a knowledge collection ({_said(row)})")
        status, member = bench.stack.post(
            f"/api/v1/knowledge/collections/{row['id']}/members", kind="text", title=name, text=text
        )
        if status >= OK:
            raise Blocked(f"an embedding model on the embed alias ({_said(member)})")
        _wait_indexed(bench, str(row["id"]))
        made[name] = slug
    agent, _ = bench.agent(
        "sales-only",
        {
            "instructions": "Answer from the organisation's knowledge. Say so if it is not there.",
            "knowledge": {"collections": [made["sales"]], "auto_retrieve": True},
            "tools": [{"server": "knowledge", "include": ["*"]}],
        },
    )
    own = bench.ask(agent, "What is the sales desk code word?")
    expect("HERON-2209" in own.text, f"its own collection was not used: {own.text[:120]}")
    other = bench.ask(agent, "What is the payroll desk code word?")
    expect(
        "OTTER-7731" not in other.text,
        "an agent bound to the sales collection answered from the payroll collection: "
        "knowledge.search reads every collection the person can read, whatever the agent binds",
    )
    return "the agent answered from its own collection and not from another"


def _wait_indexed(bench: Bench, collection: str, wait_s: float = 90) -> None:
    deadline = time.monotonic() + wait_s
    while time.monotonic() < deadline:
        rows = _rows(bench.stack.get(f"/api/v1/knowledge/collections/{collection}/documents"))
        if rows and all(row.get("status") in {"indexed", "ready"} for row in rows):
            return
        time.sleep(3)


def case_skill(bench: Bench) -> str:
    """An agent loads a skill it is bound to and follows it."""
    slug = bench.slug("skill")
    status, skill = bench.stack.post(
        "/api/v1/skills",
        slug=slug,
        name="House style",
        description="How every answer must be signed off.",
        instructionsMd="Always end the answer with the exact line: -- checked by QUARTZ desk",
    )
    expect(status < OK and isinstance(skill, dict), f"the skill was not made: {_said(skill)}")
    skill = _body(skill)
    status, body = bench.stack.post(f"/api/v1/skills/{skill['id']}:publish", changeNote="c")
    expect(status < OK, f"the skill was not published: {_said(body)}")
    agent, _ = bench.agent(
        "skilled",
        {"instructions": "Load the house style skill before you answer.", "skills": [slug]},
    )
    turn = bench.ask(agent, "Say good morning.")
    expect("QUARTZ" in turn.text, f"the skill was not followed: {turn.text[:120]}")
    return (
        f"skill loaded ({'skills.load' if turn.tried('skills.load') else 'in prompt'}) and followed"
    )


def case_memory(bench: Bench) -> str:
    """An agent with memory recalls across conversations; one with memory off does not."""
    marker = f"OPAL-{bench.stamp % 100000}"
    on, _ = bench.agent("memory-on", {"instructions": "Be brief.", "memory": {"enabled": True}})
    bench.ask(on, f"Remember this for later: my project code is {marker}.")
    recalled = bench.ask(on, "What is my project code?")
    expect(marker in recalled.text, f"not recalled: {recalled.text[:120]}")
    other = f"JADE-{bench.stamp % 100000}"
    off, _ = bench.agent("memory-off", {"instructions": "Be brief.", "memory": {"enabled": False}})
    bench.ask(off, f"Remember this for later: my locker code is {other}.")
    forgot = bench.ask(off, "What is my locker code?")
    expect(other not in forgot.text, "an agent with memory off recalled across conversations")
    return "memory on recalls in a new conversation; memory off does not"


def case_output_schema(bench: Bench) -> str:
    """A reply follows the agent's output schema, and one that cannot is not passed off as done."""
    schema = {
        "type": "object",
        "properties": {"capital": {"type": "string"}, "country": {"type": "string"}},
        "required": ["capital", "country"],
        "additionalProperties": False,
    }
    agent, _ = bench.agent(
        "shaped", {"instructions": "Answer the question.", "output": {"json_schema": schema}}
    )
    turn = bench.ask(agent, "What is the capital of France?")
    try:
        parsed = orjson.loads(turn.text)
    except orjson.JSONDecodeError as exc:
        raise AssertionError(f"the reply is not JSON: {turn.text[:100]}") from exc
    expect(str(parsed.get("capital", "")).lower() == "paris", f"wrong object: {parsed}")
    never = {
        "type": "object",
        "properties": {"n": {"type": "integer", "minimum": 5, "maximum": 1}},
        "required": ["n"],
        "additionalProperties": False,
    }
    stuck, _ = bench.agent(
        "unshapeable", {"instructions": "Answer the question.", "output": {"json_schema": never}}
    )
    failed = bench.ask(stuck, "Pick a number.")
    expect(
        failed.status != "completed",
        f"an impossible shape was reported as done: {failed.text[:80]}",
    )
    return f"matching JSON returned; an impossible schema ended as {failed.status}"


def case_budget(bench: Bench) -> str:
    """A run that reaches its limit stops, says which limit, and keeps what it made."""
    agent, _ = bench.agent(
        "tight",
        {
            "instructions": "Use one query per question. Never combine questions in one query.",
            "tools": [_GENERAL],
            "budget": {
                "max_steps": 16,
                "max_tokens": 80_000,
                "max_cost_micros": 4_000_000,
                "max_wall_clock_s": 600,
                "max_tool_calls": 2,
                "max_parallel_tool_calls": 1,
            },
        },
    )
    turn = bench.ask(
        agent,
        "From the attached file answer these one at a time, each with its own query: the "
        "count for North, for South, for East, for West, and then the total.",
        files=_TABLE,
    )
    expect("limit" in turn.text.lower(), f"the stop is not explained: {turn.text[:160]}")
    expect(len(turn.calls) <= 3, f"{len(turn.calls)} tool calls ran with a limit of 2")
    return f"stopped at the tool-call limit after {len(turn.calls)} calls and said so"


def case_model_alias(bench: Bench) -> str:
    """An agent runs on the model alias its definition names."""
    agent, _ = bench.agent(
        "fast", {"instructions": "Be brief.", "model": {"alias": "fast", "fast_alias": "fast"}}
    )
    turn = bench.ask(agent, "Say hello.")
    expect(turn.status == "completed", f"the fast alias did not answer: {turn.status}")
    status, body = bench.stack.put(
        f"/api/v1/agents/{agent}/versions/draft",
        definition={"instructions": "Be brief.", "model": {"alias": "no-such-alias"}},
        changeNote="bad",
    )
    if status < OK:
        status, body = bench.stack.post(f"/api/v1/agents/{agent}:publish", changeNote="bad")
    expect(
        status >= 400 and "alias" in str(body).lower(),
        f"an unknown alias was accepted: {_said(body)}",
    )
    return "runs on the named alias; an alias that does not exist is refused at publish"


def case_sandbox(bench: Bench) -> str:
    """An agent with a computer runs a command on it."""
    agent, _ = bench.agent(
        "computer",
        {
            "instructions": "You have a computer. Run commands on it when asked.",
            "sandbox": {"enabled": True, "template": "python-data"},
            "tools": [{"server": "sandbox", "include": ["*"]}],
        },
    )
    turn = bench.ask(agent, "Run this shell command and tell me its output: echo box-$((40 + 2))")
    if not turn.calls and "sandbox" in turn.text.lower():
        raise Blocked(f"a running computer ({turn.text[:100]})")
    expect(
        "box-42" in turn.text, f"the command's output is missing ({turn.status}): {turn.text[:140]}"
    )
    return "a command ran on the agent's computer and its output came back"


def case_grounding(bench: Bench) -> str:
    """With strict grounding an agent answers from the file and will not answer past it."""
    agent, _ = bench.agent(
        "grounded",
        {
            "instructions": "Answer only from the attached documents.",
            "output": {"grounding": "strict", "citations": "required"},
            "tools": [{"server": "documents", "include": ["*"]}],
        },
    )
    note = [("policy.md", POLICY, "text/markdown")]
    known = bench.ask(agent, "How long are access logs kept?", files=note)
    expect("7 years" in known.text or "seven years" in known.text.lower(), known.text[:140])
    unknown = bench.ask(agent, "Who is the chief executive of the company?", files=note)
    lowered = unknown.text.lower()
    refused = any(word in lowered for word in ("not", "n't", "no ", "cannot", "unable"))
    expect(refused, f"it answered past the document: {unknown.text[:160]}")
    cited = "[" in known.text
    how = "with" if cited else "WITHOUT"
    return f"answered from the file ({how} a citation); declined what is not in it"


def case_ask_a_human(bench: Bench) -> str:
    """An agent that may ask a person pauses for the answer and then uses it."""
    agent, _ = bench.agent(
        "asks",
        {
            "instructions": "Before you answer, always ask the person which colour they want, "
            "using your ask tool. Then answer with one sentence that names that colour.",
            "human": {"enabled": True},
        },
    )
    conversation, run = bench.start(agent, "Recommend a colour for my front door.")
    expect(run, "the message started no run")
    status = bench.run_status(run, until={"waiting_input", *_DONE})
    if status != "waiting_input":
        raise AssertionError(
            f"the run did not pause for a person ({status}): {bench.last(conversation).text[:120]}"
        )
    status_code, body = bench.stack.post(f"/api/v1/runs/{run}:input", text="Teal")
    expect(status_code < OK, f"the answer was refused ({status_code}): {_said(body)}")
    final = bench.run_status(run, until=_DONE)
    text = bench.last(conversation).text
    expect(final == "completed" and "teal" in text.lower(), f"{final}: {text[:140]}")
    return "paused for a person, took the answer, and used it"


def case_task_template(bench: Bench) -> str:
    """A task template of the agent fills in the request it is named on."""
    agent, _ = bench.agent(
        "templated",
        {
            "instructions": "Do the task you are given on the attached file.",
            "tools": [{"server": "documents", "include": ["*"]}],
            "task_templates": [
                {
                    "id": "retention-check",
                    "prompt": "For each item, say whether the file states it, and quote the line.",
                    "items": ["How long access logs are kept", "Who approves break-glass access"],
                }
            ],
        },
    )
    turn = bench.ask(
        agent,
        "Check this policy.",
        files=[("policy.md", POLICY, "text/markdown")],
        taskTemplate="retention-check",
    )
    lowered = turn.text.lower()
    expect(turn.status == "completed", f"the task did not finish: {turn.status} {turn.text[:120]}")
    expect(
        "7 years" in lowered and "duty manager" in lowered, f"an item is missing: {turn.text[:200]}"
    )
    missing = bench.ask(agent, "Check this policy.", taskTemplate="no-such-template")
    expect(
        missing.status.startswith("http 4"), f"an unknown template was accepted: {missing.status}"
    )
    return "both template items answered from the file; an unknown template is refused"


def case_pii_masking(bench: Bench) -> str:
    """With masking on, personal data in a file the agent reads is not passed on as written.

    The setting masks what a tool returns to the model. A person's own message is theirs
    to send, and is not masked.
    """
    address = "jane.doe@example.com"
    note = [
        (
            "contact.md",
            f"# Contact\n\nThe supplier contact is Jane Doe, {address}.\n",
            "text/markdown",
        )
    ]
    agent, _ = bench.agent(
        "masked",
        {
            "instructions": "Read the attached file with your tools and answer from it.",
            "safety": {"pii_masking": True},
            "tools": [{"server": "documents", "include": ["*"]}],
        },
    )
    turn = bench.ask(
        agent, "Read the attached file. What is the supplier's email address?", files=note
    )
    expect(turn.status == "completed", f"the masked turn did not finish: {turn.status}")
    expect(
        address not in turn.text,
        f"the address in the file came back unmasked: {turn.text[:120]}",
    )
    return f"the address in the file was not passed on: {turn.text[:90]!r}"


# --- Stage: gate -------------------------------------------------------------------------

_EVAL_DONE = {"completed", "passed", "failed", "cancelled", "error"}


def _suite(bench: Bench, agent: str, *, required: bool, expects: str) -> str:
    """A suite of one case for ``agent``: the reply to "Go." must contain ``expects``."""
    status, suite = bench.stack.post(
        "/api/v1/eval-suites",
        name=bench.slug("suite"),
        agentId=agent,
        gate={"required": required, "minPassRate": 1.0, "mustPassTags": []},
    )
    expect(status < OK and isinstance(suite, dict), f"the suite was not made: {_said(suite)}")
    suite = _body(suite)
    status, case = bench.stack.post(
        f"/api/v1/eval-suites/{suite['id']}/cases",
        name="says the word",
        input={"messages": ["Go."]},
        assertions=[{"type": "contains", "value": expects}],
    )
    expect(status < OK, f"the case was not added: {_said(case)}")
    return str(suite["id"])


def _eval_result(bench: Bench, run: str, wait_s: float = 240) -> Body:
    deadline = time.monotonic() + wait_s
    seen: object = {}
    while time.monotonic() < deadline:
        seen = bench.stack.get(f"/api/v1/eval-runs/{run}")
        if isinstance(seen, dict) and str(seen.get("status")) in _EVAL_DONE:
            return seen
        time.sleep(3)
    return seen if isinstance(seen, dict) else {}


def case_eval_run(bench: Bench) -> str:
    """A suite is run against a published agent and scores what the agent said."""
    agent, _ = bench.agent("scored", {"instructions": "Answer every message with the word DELTA."})
    suite = _suite(bench, agent, required=False, expects="DELTA")
    status, started = bench.stack.post(f"/api/v1/eval-suites/{suite}:run", agentId=agent)
    expect(status < OK and isinstance(started, dict), f"the run did not start: {_said(started)}")
    started = _body(started)
    run = str(started.get("id") or started.get("evalRunId") or "")
    result = _eval_result(bench, run)
    rate = result.get("passRate", (result.get("summary") or {}).get("passRate"))
    expect(
        str(result.get("status")) in {"completed", "passed"},
        f"the eval ended as {result.get('status')}",
    )
    expect(rate in (1, 1.0), f"the one case did not pass: pass rate {rate} {str(result)[:160]}")
    results = _rows(bench.stack.get(f"/api/v1/eval-runs/{run}/results"))
    return f"1 case run and scored, pass rate {rate}, {len(results)} result rows"


def case_case_from_conversation(bench: Bench) -> str:
    """A reply a person liked becomes a test case."""
    agent, _ = bench.agent("liked", {"instructions": "Answer every message with the word EPSILON."})
    turn_conversation, run = bench.start(agent, "Go.")
    bench.run_status(run, until=_DONE)
    seen = bench.stack.get(f"/api/v1/conversations/{turn_conversation}")
    messages = seen.get("messages") if isinstance(seen, dict) else []
    reply = next((row for row in reversed(messages or []) if row.get("role") == "assistant"), None)
    expect(reply is not None, "the conversation has no reply to keep")
    reply = _body(reply)
    status, suite = bench.stack.post("/api/v1/eval-suites", name=bench.slug("kept"), agentId=agent)
    expect(status < OK and isinstance(suite, dict), f"the suite was not made: {_said(suite)}")
    suite = _body(suite)
    status, made = bench.stack.post(
        f"/api/v1/eval-suites/{suite['id']}/cases:from-conversation",
        conversationId=turn_conversation,
        messageId=reply["id"],
    )
    expect(status < OK, f"the case was not made from the conversation ({status}): {_said(made)}")
    cases = _rows(bench.stack.get(f"/api/v1/eval-suites/{suite['id']}/cases"))
    expect(len(cases) == 1, f"the suite holds {len(cases)} cases")
    return f"one case made from a reply, with {len(cases[0].get('assertions') or [])} checks"


def case_gate_holds(bench: Bench) -> str:
    """A required suite that fails keeps the new version from being published."""
    agent = bench.create(bench.slug("gated"))
    bench.draft(agent, {"instructions": "Answer every message with the word ZETA."})
    bench.publish(agent)
    _suite(bench, agent, required=True, expects="ZETA")
    # A change that breaks the suite: the gate must hold it.
    bench.draft(agent, {"instructions": "Answer every message with the word OMEGA."})
    status, held = bench.stack.post(
        f"/api/v1/agents/{agent}:publish", changeNote="breaks the suite"
    )
    expect(
        status < OK and isinstance(held, dict),
        f"publish was refused outright ({status}): {_said(held)}",
    )
    held = _body(held)
    run = str(held.get("evalRunId") or held.get("eval_run_id") or "")
    expect(run, f"the publish was not held for the suite: {str(held)[:160]}")
    result = _eval_result(bench, run)
    time.sleep(3)
    said = bench.ask(agent, "Go.").text.upper()
    expect("ZETA" in said and "OMEGA" not in said, f"the failing version went live: {said[:60]}")
    # A change that keeps the suite passing goes through once the suite has run.
    bench.draft(agent, {"instructions": "Answer every message with the words ZETA ZETA."})
    status, again = bench.stack.post(
        f"/api/v1/agents/{agent}:publish", changeNote="keeps the suite"
    )
    again = _body(again)
    passing = str(again.get("evalRunId") or again.get("eval_run_id") or "")
    expect(status < OK and passing, f"the second publish was not held: {str(again)[:160]}")
    _eval_result(bench, passing)
    deadline = time.monotonic() + 60
    said = ""
    while time.monotonic() < deadline:
        said = bench.ask(agent, "Go.").text.upper()
        if said.count("ZETA") >= 2:
            break
        time.sleep(5)
    expect(said.count("ZETA") >= 2, f"the passing version was not published: {said[:60]}")
    return f"a failing change was held (eval {result.get('status')}); a passing one went live"


def case_gate_skip(bench: Bench) -> str:
    """Passing over a required suite takes a permission a plain publisher does not have."""
    if bench.second is None:
        raise Blocked("a second person (AR_SECOND_EMAIL, AR_SECOND_PASSWORD)")
    theirs = Bench(bench.second, None, stamp=bench.stamp, count=bench.count + 500)
    try:
        agent = theirs.create(theirs.slug("skipped"))
    except AssertionError as exc:
        raise Blocked(f"a second person who may create and publish agents ({exc})") from exc
    theirs.draft(agent, {"instructions": "Answer every message with the word ETA."})
    theirs.publish(agent)
    _suite(theirs, agent, required=True, expects="ETA")
    theirs.draft(agent, {"instructions": "Answer every message with the word OMEGA."})
    status, body = bench.second.post(
        f"/api/v1/agents/{agent}:publish", changeNote="skip", skipEvalGate=True
    )
    bench.stack.remember("agent", agent)
    expect(
        status == 403,
        f"a publisher without agents:manage_all skipped a required suite ({status}): {_said(body)}",
    )
    said = theirs.ask(agent, "Go.").text.upper()
    bench.seen.extend(theirs.seen)
    expect("OMEGA" not in said, f"the failing version went live: {said[:60]}")
    return f"refused with 403: {_said(body)[:90]!r}; the earlier version still answers"


# --- Stage: together ---------------------------------------------------------------------


def _specialist(bench: Bench, name: str, word: str) -> str:
    """A published agent that answers every message with one word. Returns its slug."""
    _agent, slug = bench.agent(
        name, {"instructions": f"Answer every message with exactly this and nothing else: {word}"}
    )
    return slug


def _lead(bench: Bench, name: str, allowed: list[str], instructions: str, **spec: object) -> str:
    agent, _slug = bench.agent(
        name,
        {"instructions": instructions, "tools": [], "subagents": {"allowed": allowed, **spec}},
    )
    return agent


def _children(bench: Bench, run: str) -> list[Body]:
    return _rows(bench.stack.get(f"/api/v1/runs/{run}/children"))


def _finish(bench: Bench, agent: str, text: str, wait_s: float = 300) -> tuple[str, str, str, str]:
    """Send one message and wait. Returns the conversation, the run, its status and the reply."""
    conversation, run = bench.start(agent, text)
    status = bench.run_status(run, until=_DONE, wait_s=wait_s)
    return conversation, run, status, bench.reply(conversation, run)


def case_call_one(bench: Bench) -> str:
    """A lead asks one specialist and passes on what it said."""
    word = f"KESTREL-{bench.stamp % 10000}"
    lead = _lead(
        bench,
        "lead-one",
        [_specialist(bench, "code-desk", word)],
        "You do not know the code word. For every message, call the code desk agent at once "
        "with the task 'What is the code word?' and report its answer.",
    )
    _conversation, run, status, text = _finish(bench, lead, "What is the code word?")
    expect(status == "completed" and word in text, f"{status}: {text[:140]}")
    children = _children(bench, run)
    expect(len(children) >= 1, "the run shows no child run")
    return f"the specialist's answer came back; the run shows {len(children)} child run"


def case_own_conversation(bench: Bench) -> str:
    """What a specialist is asked and answers stays out of the person's conversation."""
    word = f"LANTERN-{bench.stamp % 10000}"
    lead = _lead(
        bench,
        "lead-tidy",
        [_specialist(bench, "back-office", word)],
        "You are a front desk. The back office agent holds the order reference. For every "
        "message, call the back office agent at once with the task 'What is the order "
        "reference?' and report its answer. Never ask the person anything first.",
    )
    conversation, run, status, text = _finish(bench, lead, "What is my order reference?")
    expect(status == "completed" and word in text, f"{status}: {text[:140]}")
    seen = bench.stack.get(f"/api/v1/conversations/{conversation}")
    messages = seen.get("messages") if isinstance(seen, dict) else []
    mine = [row for row in messages or [] if str(row.get("runId")) == run]
    extra = [row for row in messages or [] if str(row.get("runId")) != run]
    expect(
        not extra,
        f"the person's conversation holds {len(extra)} messages of the specialist's run "
        f"beside the {len(mine)} of their own: the task the lead sent appears as a message "
        "from the person, and the specialist's answer as a second reply",
    )
    return "the conversation holds the person's message and the lead's reply, and nothing else"


def case_parallel(bench: Bench) -> str:
    """A lead asks three specialists at once and combines the three answers."""
    words = [f"{name}-{bench.stamp % 1000}" for name in ("AMBER", "COBALT", "IVORY")]
    slugs = [_specialist(bench, f"desk-{index}", word) for index, word in enumerate(words)]
    lead = _lead(
        bench,
        "lead-three",
        slugs,
        "For every message, call all three desk agents in one agents_parallel call, each "
        "with the task 'What is your word?', then list the three answers exactly as given. "
        "Never ask the person anything first.",
        max_parallel=3,
    )
    _conversation, run, status, text = _finish(bench, lead, "Collect the three words.")
    missing = [word for word in words if word not in text]
    expect(status == "completed" and not missing, f"{status}; missing {missing}: {text[:140]}")
    children = _children(bench, run)
    expect(len(children) >= 3, f"the run shows {len(children)} child runs, not three")
    return f"three answers combined; the run shows {len(children)} child runs"


def case_handoff(bench: Bench) -> str:
    """A handoff ends the lead's turn with the specialist's answer."""
    word = f"HARBOUR-{bench.stamp % 10000}"
    lead = _lead(
        bench,
        "lead-handoff",
        [_specialist(bench, "front-desk", word)],
        "You never answer yourself and never ask a question. Your only action is to hand "
        "the conversation to the front desk agent with agents_handoff, at once.",
    )
    _conversation, run, status, text = _finish(bench, lead, "Please put me through.")
    expect(status == "completed" and word in text, f"{status}: {text[:140]}")
    children = _children(bench, run)
    expect(
        len(children) == 1,
        f"the lead handed the conversation over {len(children)} times: a handoff does not end "
        "its turn, so it hands over again at every step until the step limit",
    )
    return "the reply is the specialist's own, after one handoff"


def case_cycle(bench: Bench) -> str:
    """Two agents cannot be set up to call each other: the loop is refused when it is closed."""
    first, second = bench.slug("ping"), bench.slug("pong")
    made = {first: bench.create(first), second: bench.create(second)}

    def calls(other: str) -> Body:
        return {
            "instructions": f"Always call the {other} agent with the same task.",
            "tools": [],
            "subagents": {"allowed": [other], "max_depth": 3},
        }

    # An agent can only name one that is published, so the loop is closed in three steps.
    bench.draft(made[first], {"instructions": "Say hello.", "tools": []})
    bench.publish(made[first])
    bench.draft(made[second], calls(first))
    bench.publish(made[second])
    status, body = bench.stack.put(
        f"/api/v1/agents/{made[first]}/versions/draft", definition=calls(second), changeNote="loop"
    )
    if status < OK:
        status, body = bench.stack.post(f"/api/v1/agents/{made[first]}:publish", changeNote="loop")
    expect(status >= 400, "two agents that call each other were both published")
    expect("cycle" in str(body).lower(), f"the refusal does not say why: {_said(body)}")
    return f"closing the loop was refused: {_said(body)[:80]!r}"


def case_slow_child(bench: Bench) -> str:
    """A specialist that takes too long is given up on, and the lead says so."""
    _agent, slow = bench.agent(
        "slow-desk",
        {
            "instructions": "Write a detailed essay of at least 1500 words on the task "
            "you are given."
        },
    )
    lead = _lead(
        bench,
        "lead-impatient",
        [slow],
        "Ask the slow desk agent for an essay on rivers. If it does not answer in time, say "
        "that it did not answer in time. Do not write the essay yourself.",
        child_timeout_s=2,
    )
    started = time.monotonic()
    _conversation, _run, status, text = _finish(bench, lead, "Get me the essay.")
    took = time.monotonic() - started
    expect(status == "completed", f"the lead's run ended as {status}: {text[:140]}")
    expect(len(text) < 1500, "the essay came back although the specialist had two seconds")
    return f"given up on after its time; the lead answered in {took:.0f}s: {text[:80]!r}"


def case_cancel_parent(bench: Bench) -> str:
    """Stopping the lead stops the specialist it is waiting for."""
    _agent, slow = bench.agent(
        "long-desk",
        {
            "instructions": "Write a detailed essay of at least 3000 words on the task "
            "you are given."
        },
    )
    lead = _lead(
        bench,
        "lead-stopped",
        [slow],
        "Ask the long desk agent for an essay on mountains and return it in full.",
        child_timeout_s=300,
    )
    _conversation, run = bench.start(lead, "Get me the essay.")
    # A specialist is on the run's record as soon as it starts, while the lead still waits.
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline and not _children(bench, run):
        time.sleep(1)
    started = _children(bench, run)
    expect(started, "the run shows no specialist while the lead is waiting for one")
    expect(
        any(str(row.get("status")) == "running" for row in started),
        f"the specialist is not shown as running: {[row.get('status') for row in started]}",
    )
    status, body = bench.stack.post(f"/api/v1/runs/{run}:cancel")
    expect(status < OK, f"the stop was refused ({status}): {_said(body)}")
    final = bench.run_status(run, until=_DONE, wait_s=60)
    expect(final == "cancelled", f"the lead ended as {final}")
    deadline = time.monotonic() + 60
    states: list[str] = []
    while time.monotonic() < deadline:
        states = [str(row.get("status")) for row in _children(bench, run)]
        if all(state in _DONE for state in states):
            break
        time.sleep(2)
    expect(all(state in _DONE for state in states), f"a specialist is still going: {states}")
    return f"the specialist showed as running, and ended as {states} when the lead was stopped"


def case_child_needs_approval(bench: Bench) -> str:
    """A specialist's action that needs approval is refused in words, not left hanging.

    A run another agent started has nobody to come back to after a decision, so no
    approval request is made for it. The lead says the person must ask the agent directly.
    """
    if bench.second is None:
        raise Blocked("a second person (AR_SECOND_EMAIL, AR_SECOND_PASSWORD)")
    me = bench.second.get("/api/v1/me")
    writer, problem = _approval_agent(
        bench.stack, str(me.get("id") if isinstance(me, dict) else "")
    )
    if problem:
        raise Blocked(f"an agent whose writes need approval ({problem})")
    found = bench.stack.get(f"/api/v1/agents/{writer}")
    slug = str(found.get("slug") or "") if isinstance(found, dict) else ""
    lead = _lead(
        bench,
        "lead-approval",
        [slug],
        f"You are a coordinator. Your helper agent {slug} saves files for people. Whenever "
        "the person asks for a file to be saved, call that agent with the request, word "
        "for word, and report exactly what it says, including any reason it gives.",
        child_timeout_s=120,
    )
    conversation, _run, status, text = _finish(
        bench, lead, "Save a file named handover.txt that holds only the word AGREED."
    )
    expect(status == "completed", f"the lead ended as {status}: {text[:120]}")
    expect(not _has_file(bench.stack, conversation, "handover.txt"), "written without approval")
    waiting = [
        row
        for row in _rows(bench.second.get("/api/v1/approvals"))
        if row.get("status") == "pending" and str(row.get("conversationId")) == conversation
    ]
    expect(not waiting, "an approval request was made that nothing will act on")
    expect("approv" in text.lower(), f"the lead does not say approval is needed: {text[:160]}")
    # Asked directly, the same agent holds the action for the second person and then runs it.
    direct = Chat(bench.stack, writer)
    own = direct.open()
    bench.seen.append(own)
    bench.stack.post(
        f"/api/v1/conversations/{own}/messages",
        text="Save a file named handover.txt that holds only the word AGREED.",
    )
    request, problem = _request_for(bench.stack, bench.second, own)
    expect(request is not None, f"asked directly, no approval request was made ({problem})")
    problem = _decide(bench.stack, bench.second, _body(request))
    expect(not problem, problem)
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline and not _has_file(bench.stack, own, "handover.txt"):
        time.sleep(2)
    expect(_has_file(bench.stack, own, "handover.txt"), "the approved write did not happen")
    return f"through a lead: refused in words ({text[:60]!r}); asked directly: approved and written"


STAGES: dict[str, dict[str, Callable[[Bench], str]]] = {
    "build": {
        "templates": case_templates,
        "builder": case_builder,
        "edit-and-validate": case_edit_and_validate,
        "rollback": case_rollback,
        "bundle": case_bundle,
        "visibility": case_visibility,
        "disable-and-archive": case_disable,
        "stale-edit": case_stale_edit,
    },
    "configure": {
        "tools": case_tools,
        "knowledge": case_knowledge,
        "knowledge-confined": case_knowledge_confined,
        "skill": case_skill,
        "memory": case_memory,
        "output-schema": case_output_schema,
        "budget": case_budget,
        "model-alias": case_model_alias,
        "computer": case_sandbox,
        "strict-grounding": case_grounding,
        "ask-a-human": case_ask_a_human,
        "task-template": case_task_template,
        "pii-masking": case_pii_masking,
    },
    "gate": {
        "eval-run": case_eval_run,
        "case-from-conversation": case_case_from_conversation,
        "gate-holds-a-failing-change": case_gate_holds,
        "gate-cannot-be-skipped-freely": case_gate_skip,
    },
    "together": {
        "lead-asks-one": case_call_one,
        "conversation-stays-the-persons": case_own_conversation,
        "lead-asks-three-at-once": case_parallel,
        "handoff": case_handoff,
        "two-agents-in-a-loop": case_cycle,
        "slow-specialist": case_slow_child,
        "stopping-the-lead": case_cancel_parent,
        "specialist-needs-approval": case_child_needs_approval,
    },
}


def run(bench: Bench, stages: list[str], only: list[str]) -> list[Body]:
    rows: list[Body] = []
    for stage in stages:
        for name, case in STAGES[stage].items():
            if only and name not in only:
                continue
            started = time.monotonic()
            before = len(bench.seen)
            try:
                verdict, note = "pass", case(bench)
            except Blocked as exc:
                verdict, note = "blocked", f"needs {exc}"
            except AssertionError as exc:
                verdict, note = "fail", str(exc)
            except Exception as exc:  # noqa: BLE001 — one case must not end the pass
                verdict, note = "fail", f"{type(exc).__name__}: {str(exc)[:200]}"
            row: Body = {
                "stage": stage,
                "case": name,
                "verdict": verdict,
                "note": note,
                "seconds": round(time.monotonic() - started, 1),
                "conversations": bench.seen[before:],
            }
            rows.append(row)
            print(f"{verdict:8} {stage}/{name:22} {row['seconds']:>6}s  {note[:150]}", flush=True)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", action="append", default=[], choices=sorted(STAGES))
    parser.add_argument("--case", action="append", default=[])
    parser.add_argument("--out", default="agent-certification.json")
    options = parser.parse_args()
    api = os.environ.get("AR_API_URL", "http://127.0.0.1:18010").rstrip("/")
    stack = Stack(api, os.environ["AR_ADMIN_EMAIL"], os.environ["AR_ADMIN_PASSWORD"])
    second = None
    if os.environ.get("AR_SECOND_EMAIL") and os.environ.get("AR_SECOND_PASSWORD"):
        second = Stack(api, os.environ["AR_SECOND_EMAIL"], os.environ["AR_SECOND_PASSWORD"])
    bench = Bench(stack, second)
    try:
        rows = run(bench, options.stage or list(STAGES), options.case)
    finally:
        stack.put_away()
    Path(options.out).write_bytes(orjson.dumps({"cases": rows}, option=orjson.OPT_INDENT_2))
    counts: dict[str, int] = {}
    for row in rows:
        counts[str(row["verdict"])] = counts.get(str(row["verdict"]), 0) + 1
    print(orjson.dumps(counts).decode())


if __name__ == "__main__":
    main()

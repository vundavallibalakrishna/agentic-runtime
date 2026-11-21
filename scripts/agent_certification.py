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
import hashlib
import hmac
import os
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
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
    routines: list[str] = field(default_factory=list)

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
                parts = row.get("content")
                return "".join(
                    str(part.get("text") or "")
                    for part in (parts if isinstance(parts, list) else [])
                    if isinstance(part, dict) and part.get("type") == "text"
                ) or str(row.get("text") or "")
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


# --- Stage: engine -----------------------------------------------------------------------

_ESSAY = "Write a 3000 word essay about the history of bridges."


def _stop_and_continue(bench: Bench, slug: str, tools: list[Body]) -> str:
    agent, _ = bench.agent(slug, {"instructions": "Do what the person asks.", "tools": tools})
    conversation, run = bench.start(agent, _ESSAY)
    time.sleep(12)
    status, body = bench.stack.post(f"/api/v1/runs/{run}:cancel")
    expect(status < OK, f"the stop was refused ({status}): {_said(body)}")
    asked = time.monotonic()
    final = bench.run_status(run, until=_DONE, wait_s=60)
    took = time.monotonic() - asked
    expect(final == "cancelled", f"the stopped run ended as {final}")
    expect(took < 10, f"the stop took {took:.0f}s to take effect")
    kept = bench.reply(conversation, run)
    status, resumed = bench.stack.post(f"/api/v1/runs/{run}:resume")
    expect(status < OK, f"continue was refused ({status}): {_said(resumed)[:80]}")
    again = bench.run_status(run, until=_DONE, wait_s=300)
    expect(again == "completed", f"the continued run ended as {again}")
    whole = bench.reply(conversation, run)
    chat = Chat(bench.stack, agent)
    follow = chat.send(conversation, "Reply with the single word ready.")
    expect(
        "ready" in follow.text.lower(),
        f"the conversation was not usable after a stop: {follow.status}",
    )
    expect(len(kept) > 0, "nothing the model had written was kept when it was stopped")
    return (
        f"stopped in {took:.0f}s with {len(kept)} characters kept; continued to "
        f"{len(whole)} characters; next message answered"
    )


def case_stop_and_continue(bench: Bench) -> str:
    """A run a person stops ends at once, keeps its text and can be continued."""
    return _stop_and_continue(bench, "stoppable", [_GENERAL])


def case_stop_without_tools(bench: Bench) -> str:
    """The same for an agent that has no tools."""
    return _stop_and_continue(bench, "stoppable-plain", [])


def case_one_run_at_a_time(bench: Bench) -> str:
    """A second message while a run is going is refused in words, and the first run goes on."""
    agent, _ = bench.agent("busy", {"instructions": "Do what the person asks.", "tools": []})
    conversation, run = bench.start(agent, _ESSAY)
    time.sleep(2)
    status, body = bench.stack.post(
        f"/api/v1/conversations/{conversation}/messages", text="And another thing."
    )
    expect(status == 409, f"a second message got {status}: {_said(body)}")
    said = _said(body)
    bench.stack.post(f"/api/v1/runs/{run}:cancel")
    bench.run_status(run, until=_DONE, wait_s=60)
    return f"refused with 409: {said[:80]!r}"


def _held_write(bench: Bench) -> tuple[str, str, Body]:
    """A write that waits for the second person. Returns the conversation, the run, the request."""
    if bench.second is None:
        raise Blocked("a second person (AR_SECOND_EMAIL, AR_SECOND_PASSWORD)")
    me = bench.second.get("/api/v1/me")
    writer, problem = _approval_agent(bench.stack, str(_body(me).get("id") or ""))
    if problem:
        raise Blocked(f"an agent whose writes need approval ({problem})")
    conversation, run = bench.start(
        writer, "Save a file named decision.txt that holds only the word APPROVED."
    )
    waiting, problem = _request_for(bench.stack, bench.second, conversation)
    expect(waiting is not None, f"no approval request was made ({problem})")
    return conversation, run, _body(waiting)


def case_approval_refused(bench: Bench) -> str:
    """A write the second person refuses does not happen, and the reply says so."""
    conversation, run, waiting = _held_write(bench)
    status, body = bench.second.post(  # type: ignore[union-attr]
        f"/api/v1/approvals/{waiting['id']}:decide",
        decision="reject",
        comment="not this one",
        argsHash=str(waiting.get("argsHash") or ""),
    )
    expect(status < OK, f"the refusal was not taken ({status}): {_said(body)}")
    final = bench.run_status(run, until=_DONE, wait_s=180)
    text = bench.reply(conversation, run)
    expect(final in {"completed", "failed"}, f"after a refusal the run is {final}")
    expect(not _has_file(bench.stack, conversation, "decision.txt"), "the refused write happened")
    return f"refused, nothing written, run {final}: {text[:80]!r}"


def case_approval_withdrawn(bench: Bench) -> str:
    """The person who asked can withdraw a request, and the write does not happen."""
    conversation, run, waiting = _held_write(bench)
    status, body = bench.stack.post(f"/api/v1/approvals/{waiting['id']}:cancel")
    expect(status < OK, f"the request could not be withdrawn ({status}): {_said(body)}")
    final = bench.run_status(run, until=_DONE, wait_s=180)
    expect(final in _DONE, f"after the request was withdrawn the run is {final}")
    expect(not _has_file(bench.stack, conversation, "decision.txt"), "the withdrawn write happened")
    late, _late = bench.second.post(  # type: ignore[union-attr]
        f"/api/v1/approvals/{waiting['id']}:decide",
        decision="approve",
        comment="too late",
        argsHash=str(waiting.get("argsHash") or ""),
    )
    expect(late >= 400, "a withdrawn request could still be approved")
    return f"withdrawn, nothing written, run {final}; a late approval is refused ({late})"


def case_many_steps(bench: Bench) -> str:
    """A run that needs many tool calls in a row gets through them within its limits."""
    agent, _ = bench.agent(
        "many-steps",
        {
            "instructions": "Answer each question with its own query. Never combine questions.",
            "tools": [_GENERAL],
        },
    )
    turn = bench.ask(
        agent,
        "From the attached file, with a separate query for each: the count for North, for "
        "South, for East, for West, the largest count, the smallest count, the average "
        "count, and the total. List all eight answers.",
        files=_TABLE,
    )
    made = [row for row in turn.calls if row.get("qualifiedName") == "general.query_table"]
    expect(turn.status == "completed", f"the run ended as {turn.status}: {turn.text[:120]}")
    expect("53" in turn.text and "19" in turn.text, f"answers are missing: {turn.text[:160]}")
    expect(len(made) >= 5, f"only {len(made)} queries were made")
    return f"{len(made)} queries in one run, all eight answers given"


def case_worker_restart(bench: Bench) -> str:
    """A run survives the worker that carries it out being restarted."""
    del bench
    raise Blocked(
        "a stack whose worker can be restarted alone: this one starts every process together"
    )


# --- Stage: routines ---------------------------------------------------------------------


def _routine(bench: Bench, name: str, trigger: Body, **more: object) -> tuple[str, Body]:
    """A routine on a plain agent that answers with one known word."""
    agent, _ = bench.agent(
        f"routine-{name}", {"instructions": "Do exactly what is asked. Be brief.", "tools": []}
    )
    status, made = bench.stack.post(
        "/api/v1/routines",
        name=f"{name} {uuid.uuid4().hex[:6]}",
        agentId=agent,
        instructions="Reply with the single word DELIVERED and nothing else.",
        trigger=trigger,
        **more,
    )
    expect(status < OK, f"the routine was not created ({status}): {_said(made)}")
    routine = _body(made)
    bench.routines.append(str(routine.get("id")))
    return str(routine.get("id")), routine


def _hook_of(made: Body) -> tuple[str, str]:
    """The address and secret a new webhook routine shows once."""
    shown = _body(made.get("webhook"))
    return str(shown.get("webhookUrl") or ""), str(shown.get("webhookSecret") or "")


def _routine_events(bench: Bench, routine: str) -> list[Body]:
    return _rows(bench.stack.get(f"/api/v1/routines/{routine}/events"))


def _wait_event(bench: Bench, routine: str, wanted: int, wait_s: int) -> list[Body]:
    """The routine's events once ``wanted`` of them have a run that ended."""
    deadline = time.monotonic() + wait_s
    rows: list[Body] = []
    while time.monotonic() < deadline:
        rows = _routine_events(bench, routine)
        done = [
            row
            for row in rows
            if row.get("runId")
            and _body(bench.stack.get(f"/api/v1/runs/{row['runId']}")).get("status") in _DONE
        ]
        if len(done) >= wanted:
            return rows
        time.sleep(3)
    return rows


def _run_text(bench: Bench, run: str) -> tuple[str, str]:
    seen = _body(bench.stack.get(f"/api/v1/runs/{run}"))
    conversation = str(seen.get("conversationId") or "")
    if conversation:
        bench.seen.append(conversation)
    return str(seen.get("status")), bench.reply(conversation, run) if conversation else ""


def case_routine_by_hand(bench: Bench) -> str:
    """A routine a person runs now does its work and the result can be read."""
    routine, _ = _routine(bench, "by-hand", {"type": "manual"})
    status, started = bench.stack.post(f"/api/v1/routines/{routine}:run")
    expect(status < OK, f"run now was refused ({status}): {_said(started)}")
    run = str(_body(started).get("runId") or "")
    final = bench.run_status(run, until=_DONE, wait_s=180)
    expect(final == "completed", f"the run ended as {final}")
    _, text = _run_text(bench, run)
    expect("DELIVERED" in text.upper(), f"the answer was {text[:80]!r}")
    listed = _body(bench.stack.get(f"/api/v1/routines/{routine}"))
    expect(listed.get("lastRun"), "the routine does not show its last run")
    return f"ran and answered {text.strip()[:30]!r}; last run shown"


def case_routine_by_schedule(bench: Bench) -> str:
    """A routine on a one-minute schedule runs by the clock with nobody asking."""
    routine, made = _routine(
        bench, "by-schedule", {"type": "schedule", "cron": "* * * * *", "timezone": "UTC"}
    )
    expect(made.get("nextRunAt") or made.get("nextFires"), "no next run time is shown")
    rows = _wait_event(bench, routine, 1, 200)
    fired = [row for row in rows if row.get("runId")]
    expect(fired, f"nothing ran in 200 seconds; events: {[row.get('status') for row in rows]}")
    final, text = _run_text(bench, str(fired[0]["runId"]))
    bench.stack.post(f"/api/v1/routines/{routine}:pause")
    expect(final == "completed", f"the scheduled run ended as {final}")
    expect("DELIVERED" in text.upper(), f"the scheduled answer was {text[:80]!r}")
    return f"fired by the clock ({fired[0].get('source')}), answered {text.strip()[:30]!r}"


def _hook(bench: Bench, url: str, secret: str, payload: bytes, **headers: str) -> tuple[int, Body]:
    sent = {"content-type": "application/json", **headers}
    if secret:
        stamp = int(time.time())
        digest = hmac.new(secret.encode(), f"{stamp}.".encode() + payload, hashlib.sha256)
        sent["x-ar-signature"] = f"t={stamp},v1={digest.hexdigest()}"
    response = httpx.post(f"{bench.stack.api}{url}", content=payload, headers=sent, timeout=30)
    try:
        return response.status_code, _body(response.json())
    except ValueError:
        return response.status_code, {"raw": response.text[:200]}


def case_routine_by_webhook(bench: Bench) -> str:
    """A signed call from outside starts the routine; a repeat and a bad signature do not."""
    routine, made = _routine(bench, "by-webhook", {"type": "webhook"})
    url, secret = _hook_of(made)
    expect(url and secret, "the routine gave no webhook address or secret")
    payload = orjson.dumps({"type": "order.created", "data": {"n": 1}})
    key = uuid.uuid4().hex
    first, body = _hook(bench, url, secret, payload, **{"x-idempotency-key": key})
    expect(first == 202, f"a signed call got {first}: {_said(body)}")
    again, _ = _hook(bench, url, secret, payload, **{"x-idempotency-key": key})
    forged, _ = _hook(bench, url, "not-the-secret", payload)
    unsigned, _ = _hook(bench, url, "", payload)
    rows = _wait_event(bench, routine, 1, 180)
    fired = [row for row in rows if row.get("runId")]
    expect(fired, f"the signed call started no run; events: {[r.get('status') for r in rows]}")
    final, text = _run_text(bench, str(fired[0]["runId"]))
    expect(final == "completed", f"the run ended as {final}")
    expect(again in {200, 202, 409}, f"the repeated call got {again}")
    expect(len(fired) == 1, f"the repeated call started a second run ({len(fired)} runs)")
    expect(forged in {401, 403}, f"a wrong signature got {forged}")
    expect(unsigned in {401, 403}, f"an unsigned call got {unsigned}")
    return (
        f"signed 202 and answered {text.strip()[:20]!r}; repeat {again} with no second run; "
        f"wrong signature {forged}; unsigned {unsigned}"
    )


def case_routine_pause_resume(bench: Bench) -> str:
    """A paused routine does not run, by hand or from outside; resumed, it runs again."""
    routine, made = _routine(bench, "pause", {"type": "webhook"})
    url, secret = _hook_of(made)
    status, paused = bench.stack.post(f"/api/v1/routines/{routine}:pause")
    expect(status < OK and _body(paused).get("status") == "paused", f"pause: {_said(paused)}")
    by_hand, said = bench.stack.post(f"/api/v1/routines/{routine}:run")
    outside, _ = _hook(bench, url, secret, orjson.dumps({"type": "x", "n": 1}))
    time.sleep(5)
    ran = [row for row in _routine_events(bench, routine) if row.get("runId")]
    expect(not ran, f"a paused routine ran ({len(ran)} runs)")
    status, resumed = bench.stack.post(f"/api/v1/routines/{routine}:resume")
    expect(status < OK and _body(resumed).get("status") == "active", f"resume: {_said(resumed)}")
    status, started = bench.stack.post(f"/api/v1/routines/{routine}:run")
    expect(status < OK, f"run after resume was refused ({status}): {_said(started)}")
    final = bench.run_status(str(_body(started).get("runId")), until=_DONE, wait_s=180)
    expect(final == "completed", f"the run after resume ended as {final}")
    return (
        f"paused: run now {by_hand} ({_said(said)[:40]}), outside call {outside}, no run; "
        "resumed and ran"
    )


def case_routine_daily_cap(bench: Bench) -> str:
    """A routine allowed one run a day refuses the second in words."""
    routine, _ = _routine(bench, "cap", {"type": "manual"}, maxRunsPerDay=1)
    status, started = bench.stack.post(f"/api/v1/routines/{routine}:run")
    expect(status < OK, f"the first run was refused ({status}): {_said(started)}")
    bench.run_status(str(_body(started).get("runId")), until=_DONE, wait_s=180)
    status, refused = bench.stack.post(f"/api/v1/routines/{routine}:run")
    expect(status >= 400, f"a second run in the day was accepted ({status})")
    return f"second run refused with {status}: {_said(refused)[:80]!r}"


def case_routine_overlap(bench: Bench) -> str:
    """A second call while a run is going is skipped, not run beside it."""
    agent, _ = bench.agent(
        "routine-slow", {"instructions": "Do what the person asks.", "tools": []}
    )
    status, made = bench.stack.post(
        "/api/v1/routines",
        name=f"overlap {uuid.uuid4().hex[:6]}",
        agentId=agent,
        instructions="Write a 600 word essay about canals.",
        trigger={"type": "webhook"},
        concurrencyPolicy="skip",
    )
    expect(status < OK, f"the routine was not created ({status}): {_said(made)}")
    routine = str(_body(made).get("id"))
    bench.routines.append(routine)
    url, secret = _hook_of(_body(made))
    one, _ = _hook(bench, url, secret, orjson.dumps({"type": "x", "n": 1}))
    time.sleep(3)
    two, _ = _hook(bench, url, secret, orjson.dumps({"type": "x", "n": 2}))
    expect(one == 202, f"the first call got {one}")
    rows = _wait_event(bench, routine, 1, 240)
    time.sleep(5)
    rows = _routine_events(bench, routine)
    ran = [row for row in rows if row.get("runId")]
    expect(len(ran) == 1, f"{len(ran)} runs for two overlapping calls")
    return f"second call {two}; events: {sorted(str(row.get('status')) for row in rows)}; one run"


def case_routine_transfer(bench: Bench) -> str:
    """A routine handed to another person is theirs: they see it and can run it."""
    if bench.second is None:
        raise Blocked("a second person (AR_SECOND_EMAIL, AR_SECOND_PASSWORD)")
    routine, _ = _routine(bench, "transfer", {"type": "manual"})
    me = str(_body(bench.second.get("/api/v1/me")).get("id") or "")
    before = [row.get("id") for row in _rows(bench.second.get("/api/v1/routines"))]
    status, moved = bench.stack.post(f"/api/v1/routines/{routine}:transfer", newOwnerUserId=me)
    expect(status < OK, f"the transfer was refused ({status}): {_said(moved)}")
    after = [row.get("id") for row in _rows(bench.second.get("/api/v1/routines"))]
    expect(routine in after, "the new owner does not see the routine")
    owner = _body(_body(bench.stack.get(f"/api/v1/routines/{routine}")).get("owner")).get("id")
    expect(owner == me, f"the owner shown is {owner}")
    held, _ = bench.second.post(f"/api/v1/routines/{routine}:run")
    expect(held >= 400, "a routine waiting for its new owner's review ran")
    bench.second.post(f"/api/v1/routines/{routine}:resume")
    status, started = bench.second.post(f"/api/v1/routines/{routine}:run")
    how = f"refused ({status}): {_said(started)[:60]}"
    if status < OK:
        how = bench.run_status(str(_body(started).get("runId")), until=_DONE, wait_s=180)
    seen = f"seen by the new owner (before: {routine in before})"
    return f"{seen}; status {_body(moved).get('status')}; their run: {how}"


def _mail(subject_has: str = "") -> list[Body]:
    port = os.environ.get("AR_MAILPIT_UI_HOST_PORT", "8025")
    try:
        found = httpx.get(f"http://127.0.0.1:{port}/api/v1/messages", timeout=10).json()
    except (httpx.HTTPError, ValueError) as exc:
        raise Blocked(f"the local mail server ({type(exc).__name__})") from exc
    rows = [row for row in found.get("messages", []) if isinstance(row, dict)]
    return [row for row in rows if subject_has in str(row.get("Subject") or "")]


def case_routine_delivery_email(bench: Bench) -> str:
    """A routine's result goes out by email: held for the owner first, sent once approved.

    The routine belongs to the second person and runs an agent someone else built: the
    person who built an agent may not approve what it does, so they approve in advance.
    """
    second = bench.second
    if second is None:
        raise Blocked("a second person to own the routine")
    before = len(_mail())
    to = f"reader-{uuid.uuid4().hex[:6]}@example.test"
    agent, _ = bench.agent(
        "routine-email",
        {"instructions": "Do exactly what is asked. Be brief.", "tools": []},
        visibility="tenant",
    )
    status, made = second.post(
        "/api/v1/routines",
        name=f"email {uuid.uuid4().hex[:6]}",
        agentId=agent,
        instructions="Reply with the single word DELIVERED and nothing else.",
        trigger={"type": "manual"},
        delivery=[{"type": "email", "channel": to}],
    )
    expect(status < OK, f"the routine was not created ({status}): {_said(made)}")
    routine = str(_body(made).get("id"))
    try:
        status, started = second.post(f"/api/v1/routines/{routine}:run")
        expect(status < OK, f"run now was refused ({status}): {_said(started)}")
        run = str(_body(started).get("runId"))
        deadline = time.monotonic() + 180
        final = ""
        while time.monotonic() < deadline and final not in _DONE:
            final = str(_body(second.get(f"/api/v1/runs/{run}")).get("status"))
            time.sleep(2)
        expect(final == "completed", f"the run ended as {final}")
        time.sleep(6)
        expect(len(_mail()) == before, "the email left before the owner approved it")
        waiting = [
            row
            for row in _rows(second.get("/api/v1/approvals", status="pending"))
            if str(row.get("runId") or "") == run
        ]
        expect(waiting, "no approval was raised for the email")
        status, decided = second.post(
            f"/api/v1/approvals/{waiting[0]['id']}:decide",
            decision="approve",
            argsHash=str(waiting[0].get("argsHash") or ""),
        )
        expect(status < OK, f"the approval was refused ({status}): {_said(decided)}")
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline and len(_mail()) == before:
            time.sleep(2)
        got = [row for row in _mail() if to in str(row.get("To"))]
        expect(got, "no email arrived after the approval")
        time.sleep(3)
        expect(len([row for row in _mail() if to in str(row.get("To"))]) == 1, "sent twice")
        events = _rows(second.get(f"/api/v1/routines/{routine}/events"))
        shown = [str(item.get("result")) for row in events for item in _rows(row.get("deliveries"))]
        expect(shown == ["posted"], f"the event shows {shown}, not one sent delivery")
        return f"held for approval, then delivered once to {to}; the event shows it sent"
    finally:
        second.client.delete(f"/api/v1/routines/{routine}")


def case_routine_delivery_webhook(bench: Bench) -> str:
    """A result posted to an address arrives signed; an address that is down is a failure."""
    import hashlib  # noqa: PLC0415
    import hmac  # noqa: PLC0415
    import threading  # noqa: PLC0415
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer  # noqa: PLC0415

    calls: list[tuple[dict[str, str], bytes]] = []

    class Receiver(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
            calls.append((dict(self.headers.items()), body))
            self.send_response(204)
            self.end_headers()

        def log_message(self, *_args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Receiver)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    port = server.server_address[1]
    secret = uuid.uuid4().hex
    try:
        routine, made = _routine(
            bench,
            "webhook-out",
            {"type": "manual"},
            delivery=[
                {
                    "type": "webhook",
                    "preApproved": True,
                    "config": {"url": f"http://127.0.0.1:{port}/in", "secret": secret},
                }
            ],
        )
        expect(secret not in str(made), "the signing secret is shown back")
        status, started = bench.stack.post(f"/api/v1/routines/{routine}:run")
        expect(status < OK, f"run now was refused ({status}): {_said(started)}")
        final = bench.run_status(str(_body(started).get("runId")), until=_DONE, wait_s=180)
        expect(final == "completed", f"the run ended as {final}")
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline and not calls:
            time.sleep(1)
    finally:
        server.shutdown()
        server.server_close()
    if not calls and "may not be called" in str(_routine_events(bench, routine)):
        raise Blocked("an install that may call an address on this machine")
    expect(len(calls) == 1, f"{len(calls)} calls arrived, not one")
    headers, body = calls[0]
    stamp, _, digest = str(headers.get("X-Signature") or "").partition(",v1=")
    want = hmac.new(secret.encode(), stamp[2:].encode() + b"." + body, hashlib.sha256)
    expect(digest == want.hexdigest(), "the signature does not match the secret")
    expect(b"DELIVERED" in body, f"the body does not carry the result: {body[:120]!r}")
    # The receiver is gone now: the same routine run again must report the failure.
    status, started = bench.stack.post(f"/api/v1/routines/{routine}:run")
    expect(status < OK, f"the second run was refused ({status}): {_said(started)}")
    bench.run_status(str(_body(started).get("runId")), until=_DONE, wait_s=180)
    deadline = time.monotonic() + 30
    shown: list[Body] = []
    while time.monotonic() < deadline and len(shown) < 2:
        shown = [
            item for row in _routine_events(bench, routine) for item in _rows(row.get("deliveries"))
        ]
        time.sleep(2)
    results = sorted(str(item.get("result")) for item in shown)
    expect(results == ["failed", "posted"], f"the events show {results}")
    reason = next(str(item.get("reason")) for item in shown if item.get("result") == "failed")
    return f"signed call arrived; with the address down the event says: {reason!r}"


def case_routine_delivery_preapproved(bench: Bench) -> str:
    """A delivery the owner approved in advance goes out with no further question."""
    to = f"reader-{uuid.uuid4().hex[:6]}@example.test"
    routine, _ = _routine(
        bench,
        "email-standing",
        {"type": "manual"},
        delivery=[{"type": "email", "channel": to, "preApproved": True}],
    )
    _mail()
    status, started = bench.stack.post(f"/api/v1/routines/{routine}:run")
    expect(status < OK, f"run now was refused ({status}): {_said(started)}")
    final = bench.run_status(str(_body(started).get("runId")), until=_DONE, wait_s=180)
    expect(final == "completed", f"the run ended as {final}")
    deadline = time.monotonic() + 40
    got: list[Body] = []
    while time.monotonic() < deadline and not got:
        got = [row for row in _mail() if to in str(row.get("To"))]
        time.sleep(2)
    expect(got, "no email arrived")
    return f"delivered to {to}: {str(got[0].get('Snippet') or '')[:40]!r}"


def case_routine_made_by_agent(bench: Bench) -> str:
    """An agent asked in chat to do something every day sets up a routine for it."""
    agent, _ = bench.agent(
        "routine-maker",
        {
            "instructions": "When the person asks for recurring work, set up a routine for it.",
            "tools": [{"server": "routines", "include": ["*"]}],
        },
    )
    before = {row.get("id") for row in _rows(bench.stack.get("/api/v1/routines"))}
    turn = bench.ask(
        agent, "Every weekday at 9am UTC, send me a one line summary of the day's date."
    )
    made = [
        row for row in _rows(bench.stack.get("/api/v1/routines")) if row.get("id") not in before
    ]
    for row in made:
        bench.routines.append(str(row.get("id")))
    expect(made, f"no routine was made; the agent said: {turn.text[:120]!r}")
    return f"made {made[0].get('name')!r}: {made[0].get('triggerSummary')}"


# --- Stage: outside ----------------------------------------------------------------------


def _caller(bench: Bench, name: str, **key: object) -> tuple[httpx.Client, str, str, Body]:
    """A published agent and a client that calls it from outside with its own key."""
    agent, slug = bench.agent(
        f"outside-{name}", {"instructions": "Answer in one short sentence.", "tools": []}
    )
    status, made = bench.stack.post(f"/api/v1/agents/{agent}/api-keys", label=name, **key)
    expect(status < OK, f"no key was issued ({status}): {_said(made)}")
    issued = _body(made)
    client = httpx.Client(
        base_url=bench.stack.api,
        headers={"authorization": f"Bearer {issued.get('key')}"},
        timeout=240,
    )
    return client, agent, slug, issued


def _json(response: httpx.Response) -> Body:
    try:
        return _body(response.json())
    except ValueError:
        return {"raw": response.text[:200]}


def case_api_one_shot(bench: Bench) -> str:
    """One call from outside gets one answer, with what it used."""
    client, _, slug, _ = _caller(bench, "one-shot")
    response = client.post(
        f"/v1/agents/{slug}:run", json={"text": "What is 12 + 30?", "wait": True}
    )
    reply = _json(response)
    expect(response.status_code == 200, f"got {response.status_code}: {_said(reply)}")
    bench.seen.append(str(reply.get("conversationId")))
    expect("42" in str(reply.get("output")), f"the answer was {str(reply.get('output'))[:80]!r}")
    usage = _body(reply.get("usage"))
    expect(usage.get("tokensIn") and usage.get("tokensOut"), f"no token counts: {usage}")
    gaps = [name for name in ("modelCalls", "elapsedMs") if not usage.get(name)]
    expect(not gaps, f"answered 42, but the usage on the reply shows no {' or '.join(gaps)}")
    return f"answered {reply.get('output')!r}; usage {usage}"


def case_api_conversation(bench: Bench) -> str:
    """A conversation held from outside keeps what was said earlier in it."""
    client, _, slug, _ = _caller(bench, "conversation")
    opened = client.post(f"/v1/agents/{slug}/conversations", json={})
    conversation = str(_json(opened).get("id") or _json(opened).get("conversationId") or "")
    expect(conversation, f"no conversation ({opened.status_code}): {_said(_json(opened))}")
    bench.seen.append(conversation)
    path = f"/v1/agents/{slug}/conversations/{conversation}/messages"
    first = client.post(
        path, json={"text": "Please remember that my order number is 77412.", "wait": True}
    )
    expect(first.status_code == 200, f"first message got {first.status_code}")
    second = client.post(path, json={"text": "What is my order number?", "wait": True})
    said = str(_json(second).get("output"))
    expect("77412" in said, f"the second answer did not recall the first: {said[:80]!r}")
    return f"second answer recalled the number: {said[:50]!r}"


def case_api_async_events(bench: Bench) -> str:
    """A call that does not wait gets a run to follow, its events and its answer."""
    client, _, slug, _ = _caller(bench, "async")
    response = client.post(
        f"/v1/agents/{slug}:run", json={"text": "Name one colour.", "wait": False}
    )
    started = _json(response)
    expect(response.status_code == 202, f"got {response.status_code}: {_said(started)}")
    run = str(started.get("runId"))
    deadline = time.monotonic() + 120
    seen: Body = {}
    while time.monotonic() < deadline:
        seen = _json(client.get(f"/v1/agents/{slug}/runs/{run}"))
        if seen.get("status") in _DONE:
            break
        time.sleep(2)
    expect(seen.get("status") == "completed", f"the run ended as {seen.get('status')}")
    expect(seen.get("output"), "the finished run shows no answer")
    with client.stream("GET", str(started.get("eventsUrl"))) as events:
        expect(events.status_code == 200, f"events got {events.status_code}")
        kinds = [
            line.removeprefix("event:").strip()
            for line in events.iter_lines()
            if line.startswith("event:")
        ]
    expect("run.completed" in kinds, f"the events do not end the run: {kinds[-5:]}")
    return f"202, then completed with {seen.get('output')!r}; {len(kinds)} events"


def case_api_stream(bench: Bench) -> str:
    """A streamed call gets the answer piece by piece."""
    client, _, slug, _ = _caller(bench, "stream")
    kinds: list[str] = []
    with client.stream(
        "POST",
        f"/v1/agents/{slug}:run",
        json={"text": "Count from one to twenty in words.", "wait": True, "stream": True},
    ) as events:
        expect(events.status_code == 200, f"got {events.status_code}")
        kinds.extend(
            line.removeprefix("event:").strip()
            for line in events.iter_lines()
            if line.startswith("event:")
        )
    pieces = kinds.count("message.delta")
    expect(pieces > 1, f"the answer came in {pieces} piece(s): {sorted(set(kinds))}")
    expect("run.completed" in kinds, f"the stream did not end the run: {kinds[-4:]}")
    return f"{pieces} pieces, then run.completed"


def _rpc(client: httpx.Client, path: str, method: str, params: Body | None = None) -> Body:
    sent: Body = {"jsonrpc": "2.0", "id": uuid.uuid4().hex, "method": method}
    if params is not None:
        sent["params"] = params
    response = client.post(path, json=sent)
    reply = _json(response)
    expect(response.status_code == 200, f"{method} got {response.status_code}: {_said(reply)}")
    return reply


def case_api_mcp(bench: Bench) -> str:
    """Another product's assistant finds the agent as a tool and calls it."""
    client, _, slug, _ = _caller(bench, "mcp")
    path = f"/v1/agents/{slug}/mcp"
    hello = _rpc(
        client,
        path,
        "initialize",
        {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "certification", "version": "1"},
        },
    )
    expect(_body(hello.get("result")).get("serverInfo"), f"no greeting: {hello}")
    listed = _body(_rpc(client, path, "tools/list").get("result")).get("tools")
    names = [str(row.get("name")) for row in listed] if isinstance(listed, list) else []
    mine = next((name for name in names if name.startswith("agent_")), "")
    expect(mine, f"the agent is not offered as a tool: {names}")
    called = _rpc(
        client, path, "tools/call", {"name": mine, "arguments": {"message": "What is 6 times 7?"}}
    )
    result = _body(called.get("result"))
    text = " ".join(
        str(part.get("text") or "")
        for part in (result.get("content") if isinstance(result.get("content"), list) else [])
        if isinstance(part, dict)
    )
    expect("42" in text, f"the tool answered {text[:100]!r} ({called.get('error')})")
    return f"tools {names}; {mine} answered {text[:40]!r}"


def case_api_a2a(bench: Bench) -> str:
    """Another agent reads this agent's card, sends it a message and reads the task back."""
    client, _, slug, _ = _caller(bench, "a2a")
    card = _json(client.get(f"/v1/agents/{slug}/.well-known/agent-card.json"))
    expect(str(card.get("url") or "").endswith(f"/v1/agents/{slug}/a2a"), f"card: {card}")
    path = f"/v1/agents/{slug}/a2a"
    message = {
        "role": "user",
        "messageId": uuid.uuid4().hex,
        "parts": [{"kind": "text", "text": "What is 9 times 9?"}],
    }
    task = _body(_rpc(client, path, "message/send", {"message": message}).get("result"))
    state = _body(task.get("status")).get("state")
    parts = _body(_body(task.get("status")).get("message")).get("parts")
    text = " ".join(str(part.get("text")) for part in parts) if isinstance(parts, list) else ""
    expect(state == "completed" and "81" in text, f"the task was {state}: {text[:80]!r}")
    again = _rpc(client, path, "tasks/get", {"id": task.get("id")})
    kept = _body(_body(again.get("result")).get("status")).get("state")
    expect(kept == "completed", f"the task read back as {kept} ({again.get('error')})")
    return f"card read; answered {text[:30]!r}; task read back as {kept}"


def case_api_openai(bench: Bench) -> str:
    """A program written for the OpenAI chat API talks to an agent by naming it as the model."""
    _, _, slug, _ = _caller(bench, "openai")
    status, made = bench.stack.post(
        "/api/v1/api-keys", name=f"certification {uuid.uuid4().hex[:6]}"
    )
    expect(status < OK, f"no personal key was issued ({status}): {_said(made)}")
    issued = _body(made)
    token = str(issued.get("key") or issued.get("secret") or issued.get("token") or "")
    try:
        client = httpx.Client(
            base_url=bench.stack.api, headers={"authorization": f"Bearer {token}"}, timeout=240
        )
        models = _json(client.get("/api/v1/openai/models"))
        offered = [str(row.get("id")) for row in _rows(models)]
        expect(slug in offered, f"the agent is not offered as a model: {offered or models}")
        response = client.post(
            "/api/v1/openai/chat/completions",
            json={"model": slug, "messages": [{"role": "user", "content": "What is 50 + 50?"}]},
        )
        reply = _json(response)
        expect(response.status_code == 200, f"got {response.status_code}: {_said(reply)}")
        choices = reply.get("choices")
        text = str(_body(_body(choices[0]).get("message")).get("content")) if choices else ""
        expect("100" in text, f"the answer was {text[:80]!r}")
        return f"offered as a model; answered {text[:40]!r}; usage {reply.get('usage')}"
    finally:
        if issued.get("id"):
            bench.stack.client.delete(f"/api/v1/api-keys/{issued['id']}")


def case_api_key_limits(bench: Bench) -> str:
    """A key reaches only its own agent, and stops working the moment it is revoked."""
    client, agent, slug, issued = _caller(bench, "limits")
    _, _, other, _ = _caller(bench, "limits-other")
    wrong = client.post(f"/v1/agents/{other}:run", json={"text": "Hello.", "wait": True})
    expect(wrong.status_code in {401, 403, 404}, f"another agent answered ({wrong.status_code})")
    nobody = httpx.post(
        f"{bench.stack.api}/v1/agents/{slug}:run", json={"text": "Hello.", "wait": True}, timeout=30
    )
    expect(nobody.status_code == 401, f"a call with no key got {nobody.status_code}")
    revoked = bench.stack.client.delete(f"/api/v1/agents/{agent}/api-keys/{issued.get('id')}")
    expect(revoked.status_code < OK, f"the key was not revoked ({revoked.status_code})")
    after = client.post(f"/v1/agents/{slug}:run", json={"text": "Hello.", "wait": True})
    expect(after.status_code == 401, f"a revoked key got {after.status_code}")
    return f"other agent {wrong.status_code}; no key 401; revoked key {after.status_code}"


def case_api_rate_and_quota(bench: Bench) -> str:
    """A key with a small allowance is told to slow down, and then that its month is used up."""
    client, _, slug, _ = _caller(bench, "rate", rateLimitRpm=3)
    codes = [
        client.get(f"/v1/agents/{slug}/.well-known/agent-card.json").status_code for _ in range(8)
    ]
    slowed = client.post(f"/v1/agents/{slug}:run", json={"text": "Hello.", "wait": True})
    expect(
        429 in codes or slowed.status_code == 429,
        f"eight calls on a key allowed three a minute all went through: {codes}",
    )
    capped, _, capped_slug, _ = _caller(bench, "quota", monthlyQuota=1)
    first = capped.post(f"/v1/agents/{capped_slug}:run", json={"text": "Say hi.", "wait": True})
    second = capped.post(f"/v1/agents/{capped_slug}:run", json={"text": "Say hi.", "wait": True})
    expect(first.status_code == 200, f"the first call on the quota got {first.status_code}")
    expect(
        second.status_code in {402, 403, 429}, f"past its quota the key got {second.status_code}"
    )
    return (
        f"rate: {codes.count(429)} of 8 refused with 429; quota: second call "
        f"{second.status_code} {_said(_json(second))[:60]!r}"
    )


def case_api_callback(bench: Bench) -> str:
    """A caller that leaves an address is told there when the run ends."""
    client, _, slug, _ = _caller(bench, "callback")
    response = client.post(
        f"/v1/agents/{slug}:run",
        json={"text": "Hello.", "wait": False, "callbackUrl": "https://example.com/hook"},
    )
    reply = _json(response)
    if response.status_code >= 400:
        return f"refused in words ({response.status_code}): {_said(reply)[:100]!r}"
    raise Blocked("an address outside this machine that can receive the call")


# --- Stage: research ---------------------------------------------------------------------


def _research(bench: Bench, question: str, **bounds: object) -> tuple[str, str]:
    status, started = bench.stack.post("/api/v1/research/runs", question=question, **bounds)
    expect(status < OK, f"research was not started ({status}): {_said(started)}")
    view = _body(started)
    bench.seen.append(str(view.get("conversationId")))
    return str(view.get("runId")), str(view.get("conversationId"))


def _research_end(bench: Bench, run: str, wait_s: int) -> Body:
    deadline = time.monotonic() + wait_s
    view: Body = {}
    while time.monotonic() < deadline:
        view = _body(bench.stack.get(f"/api/v1/research/runs/{run}"))
        if view.get("status") in _DONE:
            break
        time.sleep(4)
    return view


def case_research_report(bench: Bench) -> str:
    """A research question gets a plan, sources that were read, and a report that cites them."""
    run, _ = _research(
        bench,
        "What is the Model Context Protocol and who maintains it?",
        maxDepth=1,
        maxBreadth=2,
        maxWallClockS=240,
    )
    view = _research_end(bench, run, 300)
    status, report = str(view.get("status")), str(view.get("report") or "")
    sources = view.get("sources") if isinstance(view.get("sources"), list) else []
    said = str(view.get("error") or "")
    if status != "completed":
        expect(said, f"research ended as {status} at phase {view.get('phase')!r} with no reason")
        if "search" in said.lower() or "provider" in said.lower():
            raise Blocked(f"a web search provider; the product said: {said[:120]!r}")
        raise AssertionError(f"research ended as {status}: {said[:160]}")
    expect(report, "research completed with no report")
    if not sources and "not configured" in report:
        raise Blocked(f"a web search provider; the product said: {report[:150]!r}")
    expect(sources, f"a {len(report)} character report was written with no source read")
    cited = view.get("citations") if isinstance(view.get("citations"), list) else []
    expect(cited, "the report cites none of its sources")
    return f"{len(report)} character report, {len(sources)} sources, {len(cited)} citations"


def case_research_cancel(bench: Bench) -> str:
    """Research a person stops ends, and says it was stopped."""
    run, _ = _research(bench, "Compare three approaches to database replication.")
    time.sleep(5)
    if _body(bench.stack.get(f"/api/v1/research/runs/{run}")).get("status") in _DONE:
        raise Blocked("a web search provider: with none, research ends before it can be stopped")
    status, body = bench.stack.post(f"/api/v1/research/runs/{run}:cancel")
    expect(status < OK, f"the stop was refused ({status}): {_said(body)}")
    asked = time.monotonic()
    view = _research_end(bench, run, 60)
    took = time.monotonic() - asked
    expect(view.get("status") == "cancelled", f"stopped research ended as {view.get('status')}")
    return f"stopped in {took:.0f}s at phase {view.get('phase')!r}"


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
    "engine": {
        "stop-and-continue": case_stop_and_continue,
        "stop-without-tools": case_stop_without_tools,
        "one-run-at-a-time": case_one_run_at_a_time,
        "approval-refused": case_approval_refused,
        "approval-withdrawn": case_approval_withdrawn,
        "many-steps": case_many_steps,
        "worker-restart": case_worker_restart,
    },
    "routines": {
        "routine-by-hand": case_routine_by_hand,
        "routine-by-schedule": case_routine_by_schedule,
        "routine-by-webhook": case_routine_by_webhook,
        "routine-pause-resume": case_routine_pause_resume,
        "routine-daily-cap": case_routine_daily_cap,
        "routine-overlap": case_routine_overlap,
        "routine-transfer": case_routine_transfer,
        "routine-delivery-email": case_routine_delivery_email,
        "routine-delivery-preapproved": case_routine_delivery_preapproved,
        "routine-delivery-webhook": case_routine_delivery_webhook,
        "routine-made-by-agent": case_routine_made_by_agent,
    },
    "research": {
        "research-report": case_research_report,
        "research-cancel": case_research_cancel,
    },
    "outside": {
        "api-one-shot": case_api_one_shot,
        "api-conversation": case_api_conversation,
        "api-async-events": case_api_async_events,
        "api-stream": case_api_stream,
        "api-mcp": case_api_mcp,
        "api-a2a": case_api_a2a,
        "api-openai": case_api_openai,
        "api-key-limits": case_api_key_limits,
        "api-rate-and-quota": case_api_rate_and_quota,
        "api-callback": case_api_callback,
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
        for routine in bench.routines:
            stack.client.delete(f"/api/v1/routines/{routine}")
        stack.put_away()
    Path(options.out).write_bytes(orjson.dumps({"cases": rows}, option=orjson.OPT_INDENT_2))
    counts: dict[str, int] = {}
    for row in rows:
        counts[str(row["verdict"])] = counts.get(str(row["verdict"]), 0) + 1
    print(orjson.dumps(counts).decode())


if __name__ == "__main__":
    main()

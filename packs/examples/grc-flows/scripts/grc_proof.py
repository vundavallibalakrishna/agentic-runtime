#!/usr/bin/env python
"""GRC document flows, end to end, against a running stack. Prints a PASS/FAIL table.

The platform has no GRC code. These flows use the generic document, knowledge, routine and
agent features on GRC-shaped documents: a security policy in two versions, control lists
(SOC 2, ISO 27001, CCM), a data processing addendum and a vendor's draft of it, a SOC 2
report excerpt and a vendor questionnaire. The right answer to every check is known from
the fixtures, so a check fails when the platform gets the document wrong.

Flows:
  A  gap analysis      a policy judged against a control list, direct and through an agent
  B  version diff      policy v1 against v2
  C  contract review   a vendor's addendum against the standard; a rewrite a person accepts
  D  questionnaire     a vendor questionnaire answered from a knowledge collection
  E  extraction        named fields read out of a report and a policy
  F  redaction         personal data hidden before a document is shared
  G  deliverable       a gap report written as a Word file
  H  automation        the gap check as a scheduled routine, and from another system by API

    AR_API_URL=http://127.0.0.1:18010 AR_ADMIN_EMAIL=... AR_ADMIN_PASSWORD=... \\
        uv run python packs/examples/grc-flows/scripts/grc_proof.py

Exit code 1 when a check fails. Writes ``evidence-live.json`` next to the fixtures.
"""

from __future__ import annotations

import csv
import os
import sys
import time
from pathlib import Path

import httpx
import orjson

REPO = Path(__file__).resolve().parents[4]
FIX = REPO / "packs" / "examples" / "grc-flows" / "fixtures"
sys.path.insert(0, str(REPO / "scripts"))

import tool_certification as tc  # noqa: E402 - the signed-in client and chat helper live there

POLICY_V1 = "acme-information-security-policy-v1.md"
POLICY_V2 = "acme-information-security-policy-v2.md"
SOC2_REPORT = "acme-soc2-report-excerpt.md"
DPA_STANDARD = "acme-dpa-standard.md"
DPA_VENDOR = "vendor-dpa-draft.md"
CONTROLS = "soc2-cc-subset.csv"
QUESTIONS = "vendor-questionnaire.csv"
# A staff record with personal data, for the redaction flow.
STAFF_NOTE = (
    "# Access exception record\n\n"
    "Requested by Priya Raman (priya.raman@acme.example, +1 415 555 0134).\n\n"
    "The exception lets the on-call engineer use the break-glass account for 4 hours.\n"
)

RESULTS: list[tuple[str, str, bool, str]] = []
EVIDENCE: dict[str, object] = {}


def record(flow: str, check: str, ok: bool, note: str = "") -> bool:  # noqa: FBT001
    RESULTS.append((flow, check, ok, note))
    print(f"  [{'PASS' if ok else 'FAIL'}] {flow}  {check}" + (f"  ({note[:110]})" if note else ""))
    return ok


def statements(name: str) -> list[str]:
    """The control list as statements, each led by its control id."""
    with (FIX / name).open(encoding="utf-8") as handle:
        return [f"{row['control_id']}: {row['statement']}" for row in csv.DictReader(handle)]


def verdicts(result: object) -> dict[str, str]:
    """Control id to verdict, from a judge result."""
    rows = result.get("rows") if isinstance(result, dict) else None
    found: dict[str, str] = {}
    for row in rows if isinstance(rows, list) else []:
        if isinstance(row, dict):
            found[str(row.get("statement") or "").split(":", 1)[0].strip()] = str(
                row.get("verdict")
            )
    return found


def text_of(value: object) -> str:
    return orjson.dumps(value).decode().lower()


class Run:
    """One signed-in run: the documents it uploaded and the agent it made."""

    def __init__(self) -> None:
        api = os.environ.get("AR_API_URL", "http://127.0.0.1:18010").rstrip("/")
        self.stack = tc.Stack(api, os.environ["AR_ADMIN_EMAIL"], os.environ["AR_ADMIN_PASSWORD"])
        self.docs: dict[str, str] = {}
        self.agent = ""
        self.slug = f"grc-analyst-{int(time.time())}"

    def upload(self, name: str, data: bytes | None = None) -> str:
        """Put a fixture in the document library. A stamp keeps a second run's copy distinct."""
        body = data if data is not None else (FIX / name).read_bytes()
        mime = "text/csv" if name.endswith(".csv") else "text/markdown"
        stamp = f"\n\n<!-- run {self.slug} -->\n" if mime == "text/markdown" else ""
        found = self.stack.upload("/api/v1/library-documents", name, body + stamp.encode(), mime)
        self.docs[name] = found
        return found

    def make_agent(self, collection: str) -> None:
        """A document analyst: the document tools and the knowledge search, nothing else."""
        _status, made = self.stack.post(
            "/api/v1/agents", slug=self.slug, name="GRC document analyst", template="blank"
        )
        self.agent = str(made.get("id") or "") if isinstance(made, dict) else ""
        if not self.agent:
            raise SystemExit("the agent was not created")
        self.stack.remember("agent", self.agent)
        self.stack.put(
            f"/api/v1/agents/{self.agent}/versions/draft",
            definition={
                "instructions": (
                    "You work from the document library. Use the document tools to do the "
                    "work: judge and missing to test a document against statements, compare "
                    "for two documents, extract for a named value, create for a file, and "
                    "knowledge search for the knowledge collection. Base every verdict only "
                    "on the document's words and quote them. If the document says nothing, "
                    "say it is not supported. Never invent a section or a control."
                ),
                "tools": [
                    {"server": "documents", "include": ["*"]},
                    {"server": "knowledge", "include": ["search"]},
                ],
                "knowledge": {"collections": [collection]} if collection else {},
            },
            changeNote="grc flows",
        )
        self.stack.post(f"/api/v1/agents/{self.agent}:publish", changeNote="grc flows")

    def ask(self, text: str) -> tc.Turn:
        chat = tc.Chat(self.stack, self.agent)
        return chat.send(chat.open(), text)


def flow_gap(run: Run) -> None:
    """A: the policy judged against the SOC 2 control list."""
    wanted = statements(CONTROLS)
    _s, first = run.stack.post(
        f"/api/v1/library-documents/{run.docs[POLICY_V1]}:judge", statements=wanted, label="SOC 2"
    )
    v1 = verdicts(first)
    EVIDENCE["A_v1_verdicts"] = v1
    record("A", "transit encryption is supported, with a quote", v1.get("CC6.7") == "supported")
    record(
        "A",
        "MFA is not supported (v1 only recommends it)",
        v1.get("CC6.1-MFA") != "supported",
        v1.get("CC6.1-MFA", ""),
    )
    record(
        "A",
        "one-year log retention is not supported (v1 keeps 90 days)",
        v1.get("CC7.2") != "supported",
        v1.get("CC7.2", ""),
    )
    record(
        "A",
        "quarterly access review is not supported (v1 says twelve months)",
        v1.get("CC6.3") != "supported",
        v1.get("CC6.3", ""),
    )
    record(
        "A",
        "the decoy control (a Mars site) is not supported",
        v1.get("MARS-1") != "supported",
        v1.get("MARS-1", ""),
    )
    quoted = [
        row
        for row in first.get("rows", [])
        if isinstance(first, dict) and row.get("verdict") == "supported"
    ]
    record(
        "A",
        "every supported verdict carries a quote and an anchor",
        bool(quoted) and all(row.get("quote") and row.get("citation") for row in quoted),
    )
    _s, second = run.stack.post(
        f"/api/v1/library-documents/{run.docs[POLICY_V2]}:judge", statements=wanted, label="SOC 2"
    )
    v2 = verdicts(second)
    EVIDENCE["A_v2_verdicts"] = v2
    record(
        "A",
        "v2 fixes MFA, log retention and access review",
        all(v2.get(key) == "supported" for key in ("CC6.1-MFA", "CC7.2", "CC6.3")),
        str({k: v2.get(k) for k in ("CC6.1-MFA", "CC7.2", "CC6.3")}),
    )
    record("A", "the decoy is still not supported in v2", v2.get("MARS-1") != "supported")
    turn = run.ask(
        f"Test the security policy (library document {run.docs[POLICY_V1]}) against the control "
        f"list in library document {run.docs[CONTROLS]}. Which controls does the policy not "
        "meet? Give the control id, what the policy says, and the gap."
    )
    EVIDENCE["A_agent"] = {
        "calls": [row.get("qualifiedName") for row in turn.calls],
        "answer": turn.text[:2500],
    }
    record(
        "A",
        "the agent used a document tool for the request",
        any(str(row.get("qualifiedName", "")).startswith("documents.") for row in turn.calls),
        str(sorted({str(row.get("qualifiedName")) for row in turn.calls})),
    )
    low = turn.text.lower()
    record("A", "the agent names the MFA gap", "mfa" in low or "multi-factor" in low)
    record(
        "A",
        "the agent names the log retention gap",
        "90 day" in low or "retention" in low or "retained" in low or "cc7.2" in low,
    )


def flow_diff(run: Run) -> None:
    """B: what changed between the two versions of the policy."""
    _s, result = run.stack.post(
        f"/api/v1/library-documents/{run.docs[POLICY_V1]}:compare",
        otherDocumentId=run.docs[POLICY_V2],
    )
    body = text_of(result)
    EVIDENCE["B"] = result
    record("B", "the diff shows the MFA clause change", "required for all access" in body)
    record("B", "the diff shows log retention moving to 365 days", "365 days" in body)
    record(
        "B",
        "the diff shows the added vendor re-assessment clause",
        "re-assessed every year" in body,
    )


def flow_contract(run: Run) -> None:
    """C: a vendor's addendum against the standard, and a rewrite a person accepts."""
    standard, vendor = run.docs[DPA_STANDARD], run.docs[DPA_VENDOR]
    _s, result = run.stack.post(
        f"/api/v1/library-documents/{standard}:compare", otherDocumentId=vendor
    )
    body = text_of(result)
    record("C", "the comparison shows the audit clause is gone", "audit" in body)
    record("C", "the comparison shows the breach notice moving to 7 days", "7 days" in body)
    turn = run.ask(
        f"Review the vendor's data processing addendum (library document {vendor}) against our "
        f"standard (library document {standard}). List each place the vendor's draft is weaker "
        "than ours."
    )
    low = turn.text.lower()
    EVIDENCE["C_agent"] = {
        "calls": [row.get("qualifiedName") for row in turn.calls],
        "answer": turn.text[:2500],
    }
    record("C", "the agent finds the missing audit right", "audit" in low)
    record("C", "the agent finds the slower breach notice", "7 days" in low or "48 hours" in low)
    record(
        "C",
        "the agent finds the sub-processor change",
        "sub-processor" in low or "subprocessor" in low,
    )
    passages = run.stack.get(f"/api/v1/library-documents/{vendor}/passages")
    rows = passages.get("passages") if isinstance(passages, dict) else []
    anchor = next(
        (str(row.get("anchor")) for row in rows or [] if "7 days" in str(row.get("text"))), ""
    )
    _s, rewrite = run.stack.post(
        f"/api/v1/library-documents/{vendor}:rewrite",
        anchor=anchor,
        instruction=(
            "Make the breach notice 48 hours after becoming aware, not 7 days after confirming."
        ),
    )
    rewrite_id = str(rewrite.get("id") or "") if isinstance(rewrite, dict) else ""
    EVIDENCE["C_rewrite"] = rewrite
    record(
        "C",
        "a rewrite is proposed for the breach clause",
        bool(anchor and rewrite_id),
        f"anchor={anchor} status={rewrite.get('status') if isinstance(rewrite, dict) else ''}",
    )
    record("C", "the proposal says 48 hours", "48 hours" in text_of(rewrite))
    before = text_of(run.stack.get(f"/api/v1/library-documents/{vendor}/passages"))
    record("C", "nothing changes before a person accepts", "7 days" in before)
    if rewrite_id:
        status, decided = run.stack.post(
            f"/api/v1/document-rewrites/{rewrite_id}:decide", decision="accept"
        )
        EVIDENCE["C_decision"] = decided
        record("C", "a person's accept is recorded", status in {200, 201}, f"http {status}")


def flow_questionnaire(run: Run) -> None:
    """D: a vendor questionnaire answered from the knowledge collection, with citations."""
    with (FIX / QUESTIONS).open(encoding="utf-8") as handle:
        listed = "\n".join(f"{row['id']}. {row['question']}" for row in csv.DictReader(handle))
    turn = run.ask(
        "Answer this vendor questionnaire from the knowledge collection only. Give each answer "
        "on its own line, led by the question id, with a citation. Where the collection does "
        f"not support an answer, write 'needs owner input'.\n\n{listed}"
    )
    low = turn.text.lower()
    EVIDENCE["D"] = {
        "calls": [row.get("qualifiedName") for row in turn.calls],
        "answer": turn.text[:3500],
    }
    # The platform reads the collection before the turn, so a search call is not required:
    # what proves grounding is the citation on the answer.
    record(
        "D",
        "the answers cite the knowledge collection",
        turn.part("citation_ref") or turn.called("knowledge.search"),
        str(sorted({str(row.get("type")) for row in turn.parts})),
    )
    # The first answer is whatever sits between the first and the second question id.
    first = low.split("q2", 1)[0]
    record(
        "D",
        "MFA is answered as required",
        any(word in first for word in ("yes", "required", "enforced")),
        " ".join(first.split())[-60:],
    )
    record("D", "log retention is answered as 365 days", "365" in low)
    record(
        "D", "the encryption algorithm is answered as AES-256", "aes-256" in low or "aes 256" in low
    )
    # ISO 27001 and the penetration test are not in the collection. The point is that the
    # agent does not invent a yes, whichever words it uses to say so.
    uncovered = low.split("q8", 1)[-1] if "q8" in low else ""
    record(
        "D",
        "what the collection does not cover is not answered with a guess",
        bool(uncovered)
        and "yes" not in uncovered
        and any(phrase in uncovered for phrase in ("needs owner input", "not found")),
        " ".join(uncovered.split())[:100],
    )
    record("D", "answers carry citations", "[1]" in turn.text or bool(turn.part("citation_ref")))


def flow_extract(run: Run) -> None:
    """E: named fields read out of a report and a policy."""
    _s, report = run.stack.post(
        f"/api/v1/library-documents/{run.docs[SOC2_REPORT]}:extract",
        fields=["report period", "service auditor", "opinion", "number of exceptions noted"],
    )
    body = text_of(report)
    EVIDENCE["E_report"] = report
    record("E", "the auditor is read (Northgate Assurance LLP)", "northgate" in body)
    record("E", "the opinion is read (unqualified)", "unqualified" in body)
    record("E", "the report period is read", "31 march 2026" in body)
    _s, policy = run.stack.post(
        f"/api/v1/library-documents/{run.docs[POLICY_V1]}:extract",
        fields=[
            "encryption at rest algorithm",
            "security log retention period",
            "access review frequency",
        ],
    )
    EVIDENCE["E_policy"] = policy
    values = {
        str(row.get("field")): str(row.get("value") or "")
        for row in (policy.get("fields") if isinstance(policy, dict) else []) or []
        if isinstance(row, dict)
    }
    record(
        "E",
        "the encryption algorithm is AES-256",
        "aes-256" in values.get("encryption at rest algorithm", "").lower(),
        values.get("encryption at rest algorithm", ""),
    )
    record(
        "E",
        "the log retention period is 90 days",
        "90" in values.get("security log retention period", ""),
        values.get("security log retention period", ""),
    )
    record(
        "E",
        "the access review frequency is twelve months",
        "twelve" in values.get("access review frequency", "").lower()
        or "12" in values.get("access review frequency", ""),
        values.get("access review frequency", ""),
    )


def flow_redact(run: Run) -> None:
    """F: personal data hidden before a document is shared."""
    note = run.upload("access-exception-record.md", STAFF_NOTE.encode())
    _s, result = run.stack.post(f"/api/v1/library-documents/{note}:redact")
    body = text_of(result)
    EVIDENCE["F"] = result
    record("F", "the email address is hidden", "priya.raman@acme.example" not in body)
    record("F", "the phone number is hidden", "555 0134" not in body)
    record("F", "the rest of the record is kept", "break-glass" in body)


def flow_deliverable(run: Run) -> None:
    """G: the gap report as a Word file a person can download."""
    turn = run.ask(
        f"Judge the security policy (library document {run.docs[POLICY_V1]}) against these "
        "controls, then create a Word document titled 'SOC 2 gap report' with one table: "
        "control, verdict, evidence. Controls: " + " | ".join(statements(CONTROLS)[:6])
    )
    EVIDENCE["G"] = {
        "calls": [row.get("qualifiedName") for row in turn.calls],
        "answer": turn.text[:1200],
    }
    record(
        "G",
        "the agent created a document",
        turn.called("documents.create"),
        str(sorted({str(row.get("qualifiedName")) for row in turn.calls})),
    )
    files = [
        part
        for part in turn.parts
        if part.get("type") == "file" and str(part.get("name", "")).endswith(".docx")
    ]
    record(
        "G",
        "the reply carries a Word file",
        bool(files),
        str([part.get("name") for part in turn.parts if part.get("type") == "file"]),
    )
    if files:
        file_id = str(files[0].get("fileId") or files[0].get("file_id") or "")
        got = run.stack.client.get(f"/api/v1/files/{file_id}/content")
        record(
            "G",
            "the Word file downloads and is a real document",
            got.status_code == 200 and got.content[:2] == b"PK",
            f"http {got.status_code}, {len(got.content)} bytes",
        )


def flow_automation(run: Run) -> None:
    """H: the gap check on a schedule, and from another system by API."""
    wanted = " | ".join(statements(CONTROLS)[:4])
    status, routine = run.stack.post(
        "/api/v1/routines",
        name=f"Weekly policy check {run.slug}",
        agentId=run.agent,
        instructions=(
            f"Judge library document {run.docs[POLICY_V1]} against these controls and list the "
            f"ones that are not supported: {wanted}"
        ),
        trigger={"type": "schedule", "cron": "0 9 * * 1", "timezone": "UTC"},
    )
    routine_id = str(routine.get("id") or "") if isinstance(routine, dict) else ""
    record(
        "H",
        "a weekly routine is created",
        status in {200, 201} and bool(routine_id),
        f"http {status}",
    )
    if routine_id:
        status, started = run.stack.post(f"/api/v1/routines/{routine_id}:run")
        run_id = (
            str(started.get("runId") or started.get("run_id") or "")
            if isinstance(started, dict)
            else ""
        )
        record("H", "the routine runs now", status in {200, 202} and bool(run_id), f"http {status}")
        done = _wait_run(run, run_id) if run_id else {}
        summary = str(done.get("resultSummary") or "")
        EVIDENCE["H_routine"] = {"status": done.get("status"), "answer": summary[:1500]}
        record(
            "H",
            "the routine's run completes",
            done.get("status") == "completed",
            str(done.get("status")),
        )
        record(
            "H",
            "the routine's result names the MFA gap",
            "mfa" in summary.lower() or "multi-factor" in summary.lower(),
        )
        run.stack.post(f"/api/v1/routines/{routine_id}:pause")
    status, key = run.stack.post(
        f"/api/v1/agents/{run.agent}/api-keys", label="grc flows", scope="agent"
    )
    token = str(key.get("key") or "") if isinstance(key, dict) else ""
    record(
        "H",
        "an API key for the agent is created",
        status in {200, 201} and bool(token),
        f"http {status}",
    )
    if token:
        reply = httpx.post(
            f"{str(run.stack.client.base_url).rstrip('/')}/v1/agents/{run.slug}:run",
            json={
                "text": (
                    "Is multi-factor authentication required by library document "
                    f"{run.docs[POLICY_V2]}? Quote the clause."
                )
            },
            headers={"authorization": f"Bearer {token}"},
            timeout=300,
        )
        output = str(reply.json().get("output") or "") if reply.status_code == 200 else ""
        EVIDENCE["H_api"] = {"status": reply.status_code, "answer": output[:1200]}
        record(
            "H",
            "another system gets the answer by API",
            reply.status_code == 200 and "required" in output.lower(),
            f"http {reply.status_code}",
        )


def _wait_run(run: Run, run_id: str, limit: float = 300.0) -> dict[str, object]:
    deadline = time.monotonic() + limit
    seen: object = {}
    while time.monotonic() < deadline:
        seen = run.stack.get(f"/api/v1/runs/{run_id}")
        if isinstance(seen, dict) and seen.get("status") not in {"queued", "running"}:
            break
        time.sleep(3)
    return seen if isinstance(seen, dict) else {}


def _collection(run: Run) -> str:
    """A knowledge collection holding policy v2 and the SOC 2 report excerpt."""
    slug = f"trust-library-{int(time.time())}"
    _s, made = run.stack.post("/api/v1/knowledge/collections", slug=slug, name="Trust library")
    collection = str(made.get("id") or "") if isinstance(made, dict) else ""
    for name in (POLICY_V2, SOC2_REPORT):
        status, _member = run.stack.post(
            f"/api/v1/knowledge/collections/{collection}/members",
            kind="text",
            title=name,
            text=(FIX / name).read_text(encoding="utf-8"),
        )
        if status not in {200, 201, 202}:
            raise SystemExit(f"the knowledge collection did not take {name} (http {status})")
    return slug


FLOWS = {
    "A": flow_gap,
    "B": flow_diff,
    "C": flow_contract,
    "D": flow_questionnaire,
    "E": flow_extract,
    "F": flow_redact,
    "G": flow_deliverable,
    "H": flow_automation,
}


def main() -> int:
    only = [name.upper() for name in sys.argv[1:]]
    run = Run()
    try:
        for name in (POLICY_V1, POLICY_V2, SOC2_REPORT, DPA_STANDARD, DPA_VENDOR, CONTROLS):
            run.upload(name)
        run.make_agent(_collection(run))
        for name, flow in FLOWS.items():
            if only and name not in only:
                continue
            print(f"\nFlow {name}: {(flow.__doc__ or '').strip()}")
            try:
                flow(run)
            except (httpx.HTTPError, KeyError, ValueError, AttributeError) as exc:
                record(name, "the flow ran to its end", False, f"{type(exc).__name__}: {exc}")
    finally:
        run.stack.put_away()
    out = FIX.parent / "evidence-live.json"
    out.write_bytes(orjson.dumps(EVIDENCE, option=orjson.OPT_INDENT_2))
    passed = sum(1 for _flow, _check, ok, _note in RESULTS if ok)
    print(f"\nGRC flows: {passed} of {len(RESULTS)} checks passed. Evidence: {out}")
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())

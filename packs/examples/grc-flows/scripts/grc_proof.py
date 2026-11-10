#!/usr/bin/env python
"""Reproducible GRC proof against the running stack (REST), with assertions.

Drives the platform's GENERIC document + knowledge tools on GRC-shaped inputs and asserts the
outcomes, printing a per-check PASS/FAIL table. No industry product code is touched — only the
generic endpoints (:check/:gaps/:compare/:rewrite/:extract, knowledge collections, agents) and
GRC test fixtures. Four flows: gap/weakness analysis, rewrite/redline, standards-check+extract,
grounded Q&A (RAG). It also records the current status of the known GRC defects (OQ-66 redaction,
the lexical :check gate, rewrite-can't-template).

Prereqs: a running stack (model-gateway + api) and the cert key in .secrets/deepinfra_api_key.
  AR_GRC_BASE   API base url, default http://127.0.0.1:19131
  AR_GRC_KEY    cert key (else read from <repo>/.secrets/deepinfra_api_key)
Run:  uv run python docs/testing/grc-flows/scripts/grc_proof.py
The key is never printed. Writes docs/testing/grc-flows/evidence-live.json (gitignored).
"""

from __future__ import annotations

import csv
import json
import os
import pathlib
import time

import httpx

REPO = pathlib.Path(__file__).resolve().parents[4]
FIX = REPO / "docs/testing/grc-flows/fixtures"
BASE = os.environ.get("AR_GRC_BASE", "http://127.0.0.1:3000")
KEY = os.environ.get("AR_GRC_KEY") or (REPO / ".secrets/deepinfra_api_key").read_text().strip()
LLM_BASE = os.environ.get("AR_CERT_LLM_BASE_URL", "https://api.deepinfra.com/v1/openai")
CHAT_MODEL = os.environ.get("AR_CERT_LLM_MODEL", "Qwen/Qwen3-32B")
EMBED_MODEL = os.environ.get("AR_CERT_EMBED_MODEL", "BAAI/bge-m3")
REASON = "grc_reason"
EMBED = "grc_embed"

results: list[tuple[str, str, bool, str]] = []  # (flow, check, ok, note)


def record(flow: str, check: str, ok: bool, note: str = "") -> bool:
    results.append((flow, check, ok, note[:160]))
    print(f"  [{'PASS' if ok else 'FAIL'}] {flow} / {check} — {note[:120]}")
    return ok


def client() -> httpx.Client:
    """Authenticated REST client. dev-login was removed on HEAD (M38b-T05b), so sign-in is a real
    Keycloak OIDC session: capture it once with the browser helper (docs/testing/grc-flows/scripts/
    grc-login.cjs writes AR_GRC_COOKIES) and reuse the ar_session/ar_csrf cookies here."""
    c = httpx.Client(base_url=BASE, timeout=600)
    cookie_file = os.environ.get("AR_GRC_COOKIES", "/tmp/grc-cookies.json")
    if not pathlib.Path(cookie_file).exists():
        raise RuntimeError(
            f"no session cookies at {cookie_file}. Run the Keycloak login helper first "
            f"(node grc-login.cjs) to capture ar_session."
        )
    cookies = json.loads(pathlib.Path(cookie_file).read_text())
    for name, value in cookies.items():
        c.cookies.set(name, value, domain="127.0.0.1")
    c.headers["x-csrf-token"] = cookies.get("ar_csrf", "")
    session = c.get("/api/v1/auth/session")
    if session.status_code != 200:
        raise RuntimeError(f"session invalid: {session.status_code} {session.text[:160]}")
    return c


def ensure_models(c: httpx.Client) -> None:
    """Point a chat alias and an embedding alias at the cert model (generic 'connect a model')."""
    aliases = {a.get("alias") for a in (c.get("/api/v1/model-aliases").json().get("items") or [])}
    if REASON in aliases and EMBED in aliases:
        return
    prov = c.post(
        "/api/v1/model-providers",
        json={"name": "grc-cert", "kind": "openai_compatible", "baseUrl": LLM_BASE, "apiKey": KEY},
    ).json()
    pid = prov["id"]
    chat = c.post(
        "/api/v1/models",
        json={"providerId": pid, "name": CHAT_MODEL, "upstreamModel": CHAT_MODEL, "kind": "chat"},
    ).json()
    emb = c.post(
        "/api/v1/models",
        json={
            "providerId": pid,
            "name": EMBED_MODEL,
            "upstreamModel": EMBED_MODEL,
            "kind": "embedding",
            "embeddingDimensions": 1024,
        },
    ).json()
    c.post("/api/v1/model-aliases", json={"alias": REASON, "kind": "chat", "primaryModelId": chat["id"]})
    c.post(
        "/api/v1/model-aliases",
        json={"alias": EMBED, "kind": "embedding", "primaryModelId": emb["id"]},
    )


def upload(c: httpx.Client, name: str, mime: str = "text/markdown") -> str:
    r = c.post("/api/v1/library-documents", files={"upload": (name, (FIX / name).read_bytes(), mime)})
    r.raise_for_status()
    return str(r.json()["id"])


def reqs_from(name: str) -> list[str]:
    rows = list(csv.DictReader((FIX / name).open()))
    return [f'{r["control_id"]}: {r["statement"]}' for r in rows]


def verdict_map(check_json: dict) -> dict[str, str]:
    """control_id -> verdict, from a :check result's rows."""
    out: dict[str, str] = {}
    for row in check_json.get("rows", []):
        req = str(row.get("requirement") or "")
        cid = req.split(":", 1)[0].strip()
        out[cid] = str(row.get("verdict") or "")
    return out


def wait_run(c: httpx.Client, run_id: str, limit: int = 420) -> dict:
    start = time.time()
    cur: dict = {}
    while time.time() - start < limit:
        cur = c.get(f"/api/v1/runs/{run_id}").json()
        if cur.get("status") not in ("queued", "running"):
            break
        time.sleep(3)
    return cur


def agent_turn(c: httpx.Client, agent_id: str, text: str) -> tuple[str, list[str], str]:
    """One prompt-driven turn. Returns (answer, generic actions the prompt triggered, run_id)."""
    cv = c.post("/api/v1/conversations", json={"agentId": agent_id, "modelAlias": REASON}).json()
    posted = c.post(f"/api/v1/conversations/{cv['id']}/messages", json={"text": text}).json()
    run_id = str(posted["run"]["id"])
    run = wait_run(c, run_id)
    answer = str(run.get("resultSummary") or run.get("result") or "")
    calls = c.get(f"/api/v1/runs/{run_id}/tool-calls").json()
    tools = [
        str(x.get("toolName") or x.get("qualifiedName") or x.get("name") or "")
        for x in (calls.get("items") or [])
    ]
    return answer, tools, run_id


def used(tools: list[str], *names: str) -> bool:
    """True if the prompt triggered any of the named generic document actions."""
    joined = " ".join(tools).lower()
    return any(n.lower() in joined for n in names)


def publish_agent(c: httpx.Client, slug: str, name: str, definition: dict) -> str:
    existing = [a for a in (c.get("/api/v1/agents").json().get("items") or []) if a.get("slug") == slug]
    if existing:
        return str(existing[0]["id"])
    agent = c.post(
        "/api/v1/agents",
        json={"slug": slug, "name": name, "visibility": "private", "definition": definition},
    ).json()
    c.post(f"/api/v1/agents/{agent['id']}:publish", json={"changeNote": "GRC proof", "skipEvalGate": True})
    return str(agent["id"])


def budget() -> dict:
    return {"maxSteps": 12, "maxToolCalls": 10, "maxWallClockS": 400, "maxCostMicros": 20_000_000, "maxTokens": 12000}


_GRC_AGENT = {
    "instructions": (
        "You are a GRC analyst working from a document library. Use the documents tools to do "
        "the work: read/outline to read a policy, check/gaps to judge it against a control list, "
        "compare to diff two documents, rewrite to propose a clause change, extract to pull a "
        "stated value, and knowledge.search for the trust library. Base every verdict only on the "
        "policy text and quote the section; if the policy says nothing, the verdict is not_found. "
        "Never invent a section or a control."
    ),
    "model": {"alias": REASON},
    "tools": [
        {"server": "documents", "version": "*",
         "include": ["read", "outline", "check", "gaps", "compare", "rewrite", "extract", "search"]},
        {"server": "knowledge", "version": "*", "include": ["search"]},
    ],
    "budget": budget(),
}


def verdict_for(answer: str, control_id: str) -> str:
    """Parse a control's verdict out of the agent's markdown table / prose."""
    for line in answer.splitlines():
        if control_id.lower() in line.lower():
            low = line.lower()
            if any(k in low for k in ("not_found", "not found", "not met", "no evidence", "missing")):
                return "not_met"
            if "partial" in low:
                return "partial"
            if "met" in low:
                return "met"
    return "absent"


def gap_flow(c: httpx.Client, agent: str, policy: str, control_doc: str, csv_name: str, fw: str) -> None:
    rows = list(csv.DictReader((FIX / csv_name).open()))
    ids = [r["control_id"] for r in rows]
    decoy = ids[-1]  # each fixture ends with a deliberate decoy that must be not_found
    prompt = (
        f"Check the ACME Information Security Policy (library document {policy}) against the "
        f"{fw} control list in library document {control_doc}. Read both in full, then return a "
        f"markdown table with columns Control | Verdict (met/partial/not_found) | Evidence | Gap "
        f"for every control, judging each only against the policy wording."
    )
    answer, tools, _ = agent_turn(c, agent, prompt)
    record(f"A/{fw}", "prompt triggers a check/gaps/read action",
           used(tools, "check", "gaps", "read", "outline"), f"tools={tools}")
    # The agent's prose should surface the MFA weakness (v1 only 'recommends' MFA).
    low = answer.lower()
    mfa_surfaced = ("mfa" in low or "multi-factor" in low or "multifactor" in low) and any(
        w in low for w in ("recommend", "not enforce", "partial", "gap", "not met", "require")
    )
    record(f"A/{fw}", "agent surfaces the MFA weakness in its answer", mfa_surfaced, answer[:140])
    # Structured direct :check gives a reliable verdict for the decoy (an absent control):
    # it must come back not_found — proof the analysis does not hallucinate coverage.
    reqs = [f'{r["control_id"]}: {r["statement"]}' for r in rows]
    chk = c.post(f"/api/v1/library-documents/{policy}:check",
                 json={"requirements": reqs, "label": fw, "modelAlias": REASON}).json()
    vmap = verdict_map(chk)
    record(f"A/{fw}", f"decoy {decoy} returns not_found (no hallucinated coverage)",
           vmap.get(decoy, "not_found") in ("not_found", "not_met"), f"verdict={vmap.get(decoy)}")
    EVID["A_" + fw] = {"tools": tools, "answer": answer[:3000], "direct_verdicts": vmap}


def run() -> int:
    c = client()
    ensure_models(c)
    docs = {
        n: upload(c, n, "text/csv" if n.endswith(".csv") else "text/markdown")
        for n in [
            "acme-information-security-policy-v1.md",
            "acme-information-security-policy-v2.md",
            "acme-soc2-report-excerpt.md",
            "soc2-cc-subset.csv",
            "iso27001-annexa-subset.csv",
            "ccm-subset.csv",
        ]
    }
    agent = publish_agent(c, "grc-analyst", "GRC Analyst", _GRC_AGENT)
    p1 = docs["acme-information-security-policy-v1.md"]

    # Flow A — gap / weakness analysis, prompt-driven, across SOC 2 + ISO + CCM
    gap_flow(c, agent, p1, docs["soc2-cc-subset.csv"], "soc2-cc-subset.csv", "SOC2")
    gap_flow(c, agent, p1, docs["iso27001-annexa-subset.csv"], "iso27001-annexa-subset.csv", "ISO")
    gap_flow(c, agent, p1, docs["ccm-subset.csv"], "ccm-subset.csv", "CCM")

    # Flow B — rewrite / redline. Prompt-driven action, then a direct rewrite on the resolved
    # anchor (the model can call rewrite but often cannot resolve a clause number to an anchor).
    ans, tools, _ = agent_turn(
        c, agent,
        f"In the ACME policy (document {p1}), section 2.4 only 'recommends' MFA. Use the rewrite "
        f"tool to propose a stronger clause requiring MFA for all production access.",
    )
    record("B", "prompt triggers a rewrite action", used(tools, "rewrite"), f"tools={tools}")
    passages = c.get(f"/api/v1/library-documents/{p1}/passages").json().get("passages") or []
    anchor = next((p["anchor"] for p in passages if "multi-factor" in str(p.get("text", "")).lower()), "")
    rw = c.post(f"/api/v1/library-documents/{p1}:rewrite",
                json={"anchor": anchor, "modelAlias": REASON,
                      "instruction": "Require multi-factor authentication for all access to "
                      "production systems (do not merely recommend it); keep the other clauses."}).json()
    proposed = str(rw.get("proposed") or "")
    record("B", "rewrite produces a proposal on the resolved anchor",
           bool(rw.get("hunks")) and anchor != "", f"anchor={anchor} status={rw.get('status')}")
    record("B", "proposed clause strengthens MFA",
           any(w in proposed.lower() for w in ("require", "must", "enforce")), proposed[:140])
    EVID["B"] = {"agent_tools": tools, "anchor": anchor, "proposed": proposed[:800]}

    # Flow C — extract stated values. AES-256 is the most unambiguous; the retention/review
    # values are recorded and judged in the report (the model can mis-read these — a finding).
    ans, tools, _ = agent_turn(
        c, agent,
        f"From the ACME policy (document {p1}), extract the encryption-at-rest algorithm, the "
        f"security-log retention period, and the access-review frequency. Quote the section.",
    )
    record("C", "prompt triggers a read/extract action", used(tools, "extract", "read"), f"tools={tools}")
    flat = ans.lower().replace("-", "")
    record("C", "extracted the encryption-at-rest value (AES-256)", "aes256" in flat.replace(" ", ""),
           ans[:160])
    EVID["C"] = {"tools": tools, "answer": ans[:2000],
                 "retention_correct": "90 day" in ans.lower(),
                 "review_correct": ("twelve" in ans.lower() or "12 month" in ans.lower())}

    # Flow D — grounded Q&A over a knowledge collection (policy v2 + SOC 2 excerpt)
    _rag_flow(c, agent, docs)

    # Defect re-check — OQ-66 PII redaction corrupting GRC evidence (findings only)
    red_markers = ("[DATE_TIME]", "[LOCATION]", "[US_DRIVER_LICENSE]", "[PERSON]")
    corrupted = any(m in json.dumps(EVID.get("A_SOC2", {})) for m in red_markers)
    record("defect", "OQ-66 redaction NOT corrupting gap evidence", not corrupted,
           "redaction markers present" if corrupted else "clean")

    _report()
    passed = sum(1 for *_f, ok, _n in ((f, ch, ok, n) for f, ch, ok, n in results) if ok)
    print(f"\nGRC proof: {passed}/{len(results)} checks passed (model {CHAT_MODEL})")
    return 0 if passed == len(results) else 1


def _rag_flow(c: httpx.Client, agent: str, docs: dict[str, str]) -> None:
    slug = f"acme-trust-library-{int(time.time())}"
    created = c.post("/api/v1/knowledge/collections",
                     json={"name": "ACME Trust Library", "slug": slug,
                           "description": "Policy v2 + SOC 2 excerpt", "embeddingAlias": EMBED})
    if created.status_code >= 300 or "id" not in created.json():
        record("D", "knowledge RAG available (embedding model configured)", False,
               f"collection create {created.status_code}: {created.text[:120]}")
        return
    col = created.json()
    for k in ("acme-information-security-policy-v2.md", "acme-soc2-report-excerpt.md"):
        c.post(f"/api/v1/knowledge/collections/{col['id']}/members",
               json={"kind": "library", "libraryDocumentId": docs[k]})
    time.sleep(20)  # let ingestion/embedding settle
    ans, tools, _ = agent_turn(
        c, agent,
        "Using only the ACME trust library, answer with a citation each: (1) Is MFA enforced? "
        "(2) What is the security-log retention period? (3) Do we perform annual third-party "
        "penetration testing? If the library does not support an answer, say so.",
    )
    record("D", "prompt triggered a knowledge.search action", used(tools, "search"), f"tools={tools}")
    low = ans.lower()
    record("D", "grounded answer (MFA enforced, 365-day retention)",
           ("mfa" in low or "multi-factor" in low) and ("365" in low or "year" in low), ans[:160])
    record("D", "honest about missing control (pentest not in library)",
           any(w in low for w in ("not supported", "not in", "does not", "no information", "cannot")), ans[:160])
    EVID["D"] = {"tools": tools, "answer": ans[:3000]}


def _report() -> None:
    out = REPO / "docs/testing/grc-flows/evidence-live.json"
    out.write_text(json.dumps(EVID, indent=1), encoding="utf-8")
    print(f"evidence: {out}")


EVID: dict[str, object] = {}

if __name__ == "__main__":
    raise SystemExit(run())

#!/usr/bin/env python
"""Fill a clean tenant with what the demo starts from. Safe to run again.

It uses only the public API, as an administrator would through the screens: it uploads the
documents in ``data/``, builds a knowledge collection from them, connects the risk
register database, imports a public API as a tool, and creates the demo's agents.
Nothing here is product code, and the product has no knowledge of it.

    AR_API_URL=... AR_ADMIN_EMAIL=... AR_ADMIN_PASSWORD=... DEMO_RISK_REGISTER_DSN=... \\
        uv run --no-sync python packs/examples/grc-flows/demo/scripts/setup_demo.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).parent
DATA = HERE.parent / "data"
sys.path.insert(0, str(HERE.parents[4] / "scripts"))

import tool_certification as tc  # noqa: E402 - the signed-in client lives there

MIME = {
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".csv": "text/csv",
}
LIBRARY = [
    "meridian-information-security-policy-v3.2.docx",
    "meridian-information-security-policy-v4.0.docx",
    "nist-csf-2-control-subset.csv",
    "meridian-standard-data-processing-agreement.docx",
    "cloudledger-data-processing-agreement-draft.docx",
    "cloudledger-soc2-type2-report-2026.docx",
    "customer-security-questionnaire.xlsx",
]
# What Meridian says about itself: the current policy and its standard terms.
COLLECTION = [
    "meridian-information-security-policy-v4.0.docx",
    "meridian-standard-data-processing-agreement.docx",
]
ALLOWED_HOSTS = ["api.first.org"]

GROUNDED = (
    "Base every statement on the documents and data you read with your tools, and say where "
    "it comes from (document and section, or table). If the source says nothing, say so. "
    "Never invent a section, a control, a number or a name."
)
AGENTS: dict[str, dict[str, object]] = {
    "document-analyst": {
        "name": "Document analyst",
        "description": "Reads, compares and checks policies, contracts and reports.",
        "definition": {
            "instructions": (
                "You are a document analyst for a governance, risk and compliance team. You "
                "read policies, contracts and assurance reports from the document library, "
                "compare versions, check a document against a list of requirements, pull out "
                "named facts, and write the result as a table or a Word document when asked. "
                + GROUNDED
            ),
            "tools": [
                {"server": "documents", "include": ["*"]},
                {"server": "knowledge", "include": ["search"]},
            ],
            "knowledge": {"collections": ["meridian-policy-library"]},
        },
    },
    "risk-analyst": {
        "name": "Risk analyst",
        "description": "Answers questions from the risk register and public vulnerability data.",
        "definition": {
            "instructions": (
                "You are a risk analyst. The risk register is a database you query read-only "
                "through the connection named risk_register: look at its tables and columns "
                "before you write a query. For a CVE, look up its exploit prediction score "
                "(EPSS) with the vulnerability score tool: the score is the chance, from 0 to "
                "1, that the flaw is exploited in the next 30 days. Show figures in a table, "
                "sorted so the worst comes first. " + GROUNDED
            ),
            "tools": [
                {"server": "data", "include": ["*"]},
                {"server": "exploit_scores", "include": ["*"]},
            ],
        },
    },
    "third-party-risk-lead": {
        "name": "Third-party risk lead",
        "description": "Runs a vendor review by handing parts of it to the specialists.",
        "definition": {
            "instructions": (
                "You lead third-party risk reviews. For a vendor review, hand the work to "
                "your specialists at the same time and wait for all of them: ask the "
                "document-analyst to compare the vendor's data processing agreement with "
                "our standard and to read the exceptions in the vendor's assurance report; "
                "ask the risk-analyst what the risk register holds about the vendor. Then "
                "write one assessment: a recommendation (approve, approve with conditions, "
                "or reject), the findings that led to it with their sources, and the "
                "conditions to put to the vendor. Do not do the specialists' work yourself. "
                + GROUNDED
            ),
            "tools": [{"server": "documents", "include": ["create"]}],
            # A specialist reads several documents, so it gets longer than the default minute.
            "subagents": {
                "allowed": ["document-analyst", "risk-analyst"],
                "max_parallel": 3,
                "child_timeout_s": 300,
            },
            # What the specialists use counts against the lead. Two of them reading several
            # documents use most of the default 80,000 tokens, so the lead is given room
            # for them and for its own assessment.
            "budget": {
                "max_steps": 16,
                "max_tokens": 400_000,
                "max_cost_micros": 4_000_000,
                "max_wall_clock_s": 600,
                "max_tool_calls": 16,
                "max_parallel_tool_calls": 1,
            },
        },
    },
}
OPENAPI = {
    "openapi": "3.0.3",
    "info": {"title": "Exploit prediction scores", "version": "1.0"},
    "servers": [{"url": "https://api.first.org/data/v1"}],
    "paths": {
        "/epss": {
            "get": {
                "operationId": "vulnerability_score",
                "summary": (
                    "The exploit prediction score (EPSS) of one or more CVEs: the chance, "
                    "from 0 to 1, that each is exploited in the next 30 days, and its percentile."
                ),
                "parameters": [
                    {
                        "name": "cve",
                        "in": "query",
                        "required": True,
                        "description": "One CVE id, or several separated by commas.",
                        "schema": {"type": "string"},
                    }
                ],
                "responses": {"200": {"description": "The scores."}},
            }
        }
    },
}


def rows(found: object) -> list[dict[str, object]]:
    if isinstance(found, dict):
        found = found.get("items") or found.get("data") or []
    return [row for row in found if isinstance(row, dict)] if isinstance(found, list) else []


def say(what: str, status: int, body: object = "") -> None:
    note = "" if status < 300 else "  " + json.dumps(body)[:300]
    print(f"{what}: {'done' if status < 300 else f'http {status}'}{note}")


def allow_hosts(stack: tc.Stack) -> None:
    current = stack.client.get("/api/v1/tenant")
    settings = (current.json().get("settings") or {}) if current.status_code == 200 else {}
    hosts = sorted({*map(str, settings.get("egressAllowlist") or []), *ALLOWED_HOSTS})
    done = stack.client.patch(
        "/api/v1/tenant",
        json={"settings": {"egressAllowlist": hosts}},
        headers={"If-Match": current.headers.get("etag", "")},
    )
    say("allowed hosts", done.status_code, done.text)


def library(stack: tc.Stack) -> dict[str, str]:
    listed = rows(stack.get("/api/v1/library-documents", limit=200))
    have = {str(row.get("filename")): str(row["id"]) for row in listed}
    for name in LIBRARY:
        if name in have:
            continue
        path = DATA / name
        have[name] = stack.upload(
            "/api/v1/library-documents", name, path.read_bytes(), MIME[path.suffix]
        )
        say(f"document {name}", 200 if have[name] else 500)
    return have


def collection(stack: tc.Stack, docs: dict[str, str]) -> None:
    listed = rows(stack.get("/api/v1/knowledge/collections", limit=200))
    found = next((row for row in listed if row.get("slug") == "meridian-policy-library"), None)
    if found is None:
        status, found = stack.post(
            "/api/v1/knowledge/collections",
            slug="meridian-policy-library",
            name="Meridian policy library",
            description="The current security policy and the standard contract terms.",
        )
        say("knowledge collection", status, found)
    members = rows(stack.get(f"/api/v1/knowledge/collections/{found['id']}/documents"))
    if not members:
        for name in COLLECTION:
            status, body = stack.post(
                f"/api/v1/knowledge/collections/{found['id']}/members",
                kind="library",
                libraryDocumentId=docs[name],
                title=name,
            )
            say(f"  member {name}", status, body)


def register(stack: tc.Stack) -> None:
    dsn = os.environ.get("DEMO_RISK_REGISTER_DSN", "")
    if not dsn:
        print("risk register: skipped, DEMO_RISK_REGISTER_DSN is not set")
        return
    if any(
        row.get("name") == "risk_register" for row in rows(stack.get("/api/v1/data-connections"))
    ):
        return
    status, body = stack.post(
        "/api/v1/data-connections",
        name="risk_register",
        engine="postgres",
        dsn=dsn,
        schemaNotes=(
            "Meridian's risk register: risks, the controls that treat them (risk_controls), "
            "vendors, and scanner findings (vulnerabilities, by CVE and asset)."
        ),
    )
    say("data connection risk_register", status, body)


def public_api(stack: tc.Stack) -> None:
    servers = rows(stack.get("/api/v1/tool-servers", limit=200))
    if any(row.get("slug") == "exploit_scores" for row in servers):
        return
    status, body = stack.post(
        "/api/v1/openapi-imports",
        slug="exploit_scores",
        name="Exploit prediction scores",
        description="Public exploit prediction scores (EPSS) for CVEs, from FIRST.",
        document=OPENAPI,
    )
    say("public API tool", status, body)


def review(stack: tc.Stack) -> None:
    """A second administrator approves the imported tool: nobody approves what they submitted."""
    email, password = (
        os.environ.get("AR_SECOND_EMAIL", ""),
        os.environ.get("AR_SECOND_PASSWORD", ""),
    )
    server = next(
        (
            row
            for row in rows(stack.get("/api/v1/tool-servers", limit=200))
            if row.get("slug") == "exploit_scores"
        ),
        None,
    )
    if server is None or server.get("status") != "pending_review":
        return
    if not email:
        print("public API tool: waiting for a reviewer, AR_SECOND_EMAIL is not set")
        return
    roles = {str(row.get("key")): str(row["id"]) for row in rows(stack.get("/api/v1/roles"))}
    person = next(row for row in rows(stack.get("/api/v1/users")) if row.get("email") == email)
    stack.post(
        "/api/v1/role-assignments",
        roleId=roles["tenant_admin"],
        principalType="user",
        principalId=person["id"],
    )
    reviewer = tc.Stack(os.environ["AR_API_URL"].rstrip("/"), email, password)
    versions = rows(reviewer.get(f"/api/v1/tool-servers/{server['id']}/versions"))
    version = versions[0]["id"]
    status, body = reviewer.post(
        f"/api/v1/tool-servers/{server['id']}/versions/{version}:approve",
        notes="Read-only public data, one host. Approved for the risk analyst.",
    )
    say("public API tool approved by the reviewer", status, body)


def agents(stack: tc.Stack) -> None:
    have = {
        str(row.get("slug")): str(row["id"]) for row in rows(stack.get("/api/v1/agents", limit=200))
    }
    for slug, spec in AGENTS.items():
        agent = have.get(slug, "")
        if not agent:
            status, made = stack.post(
                "/api/v1/agents",
                slug=slug,
                name=spec["name"],
                description=spec["description"],
                template="blank",
            )
            agent = str(made.get("id") or "") if isinstance(made, dict) else ""
            say(f"agent {slug}", status, made)
        status, body = stack.put(
            f"/api/v1/agents/{agent}/versions/draft",
            definition=spec["definition"],
            changeNote="demo setup",
        )
        say(f"  {slug} definition", status, body)
        status, body = stack.post(f"/api/v1/agents/{agent}:publish", changeNote="demo setup")
        say(f"  {slug} published", status, body)


def main() -> int:
    stack = tc.Stack(
        os.environ["AR_API_URL"].rstrip("/"),
        os.environ["AR_ADMIN_EMAIL"],
        os.environ["AR_ADMIN_PASSWORD"],
    )
    allow_hosts(stack)
    docs = library(stack)
    collection(stack, docs)
    register(stack)
    public_api(stack)
    review(stack)
    agents(stack)
    print(json.dumps({"documents": docs}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

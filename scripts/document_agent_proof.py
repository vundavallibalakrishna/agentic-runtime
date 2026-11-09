#!/usr/bin/env python
"""Prove the real chat / agentic flows produce correct document outputs, with a real model.

Where scripts/document_toolchain.py drives each document tool directly on a real input, this
drives the whole **agent loop**: a real model reads a natural-language instruction, chooses
and chains the document / spreadsheet / PDF / chart / OCR tools itself, and the produced
artifact is checked — the spreadsheet total is right, the created PDF really contains the
marker (pypdf reads it back), a chart PNG is produced, an attached document is quoted, and a
scanned attachment is read. This is the "test the real chat and agentic flows with docs,
excels and pdfs" proof.

It runs in process on the demo tenant with the reasoning alias pointed at the cert model —
the same live path the gym uses. Run:

  AR_EVAL_GYM_LIVE=1 AR_CERT_LLM_API_KEY=... uv run python scripts/document_agent_proof.py

The cert key is read from the environment and never printed.
"""

from __future__ import annotations

import asyncio
import io
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

import pypdf

from ar_domain.agents.service import AgentLifecycle
from ar_domain.chat.service import demo_id
from ar_domain.evals.gym.live import install_live, live_settings
from ar_testing.demo import demo_store

if TYPE_CHECKING:
    from ar_domain.chat.service import ChatService

_FIXTURES = Path("docs/testing/fixtures/m33b")


def _definition() -> dict[str, object]:
    """An agent bound to the document / data tools, told to use them and not guess."""
    return {
        "persona": {"display_name": "Document agent", "greeting": "Share a document task."},
        "instructions": (
            "You work with documents, spreadsheets and PDFs. Always use a tool to do the "
            "work — run code or query a table for a calculation, create a document to "
            "produce a file, make a chart to plot figures, read or OCR an attached file to "
            "quote from it. Never work a number out in your head, and quote the tool result."
        ),
        "model": {"alias": "reasoning"},
        "tools": [
            {
                "server": "general",
                "version": "*",
                "include": ["code", "query_table", "export_table", "chart", "read_file"],
            },
            {
                "server": "documents",
                "version": "*",
                "include": ["create", "ingest", "read", "summarise", "ocr"],
            },
        ],
        "budget": {
            "max_steps": 10,
            "max_tokens": 16000,
            "max_cost_micros": 2_000_000,
            "max_wall_clock_s": 180,
            "max_tool_calls": 8,
        },
    }


def _agent(store: ChatService) -> uuid.UUID:
    agent = AgentLifecycle(store)._insert(
        demo_id("tenant"),
        demo_id("admin"),
        slug="document-agent-proof",
        name="Document agent proof",
        description="Exercises the document tools through the agent loop.",
        visibility="tenant",
        published=True,
        definition=_definition(),
    )
    return uuid.UUID(str(agent["id"]))


def _attach(store: ChatService, data: bytes, name: str, media: str) -> uuid.UUID:
    # The real upload path builds the full file row (owner, av status, object key, preview).
    row = store.upload(demo_id("tenant"), demo_id("admin"), name, media, data)
    return uuid.UUID(str(row["id"]))


async def _chat(
    store: ChatService, agent_id: uuid.UUID, text: str, attachments: list[uuid.UUID] | None = None
) -> tuple[list[str], str, list[bytes]]:
    """Run one turn; return (tools used, answer, bytes of files produced during the turn)."""
    tenant, user = demo_id("tenant"), demo_id("admin")
    before = set(store.blobs)
    conversation = store.create_conversation(tenant, user, agent_id, model_alias="reasoning")
    posted = store.post_message(
        tenant,
        user,
        uuid.UUID(str(conversation["id"])),
        text,
        attachment_ids=attachments or [],
        schedule=False,
    )
    run = posted.get("run")
    if not isinstance(run, dict):
        raise TypeError("post_message returned no run")
    run_id = uuid.UUID(str(run["id"]))
    await store.generate(run_id, text, [])
    finished = store.runs[run_id]
    assistant = store.messages.get(uuid.UUID(str(finished.get("assistant_message_id"))))
    answer = str(assistant.get("text") or "") if isinstance(assistant, dict) else ""
    tools = [
        str(row.get("qualified_name") or "")
        for row in store.tool_calls.values()
        if row.get("run_id") == run_id
    ]
    produced = [store.blobs[fid] for fid in set(store.blobs) - before]
    return tools, answer, produced


def _pdf_text(blob: bytes) -> str:
    try:
        reader = pypdf.PdfReader(io.BytesIO(blob))
        return "\n".join(p.extract_text() or "" for p in reader.pages)
    except Exception:  # noqa: BLE001 - a non-PDF blob simply has no text
        return ""


# --- tasks: each returns (passed, note) ---------------------------------------------------
async def _spreadsheet_total(store: ChatService, agent_id: uuid.UUID) -> tuple[bool, str]:
    text = (
        "Here is regional revenue as CSV:\n"
        "region,amount\nEMEA,10432\nAPAC,7218\nAMER,8591\n"
        "Build a spreadsheet from it and tell me the total amount."
    )
    tools, answer, _ = await _chat(store, agent_id, text)
    used = any(t.split(".")[-1] in {"code", "query_table", "export_table", "create"} for t in tools)
    return (
        "26241" in answer.replace(",", "") and used
    ), f"tools={tools or 'none'}; total in answer={'26241' in answer.replace(',', '')}"


async def _pdf_marker(store: ChatService, agent_id: uuid.UUID) -> tuple[bool, str]:
    marker = "VERIFYDOC4471"
    text = (
        f"Create a one-page PDF titled 'Board Brief'. Its body must contain the exact marker "
        f"{marker}. After creating it, confirm you did."
    )
    tools, _answer, produced = await _chat(store, agent_id, text)
    hit = any(marker in _pdf_text(b).replace(" ", "") for b in produced)
    pdfs = sum(1 for b in produced if b[:4] == b"%PDF")
    return hit, f"tools={tools or 'none'}; pdfs produced={pdfs}; marker read back={hit}"


async def _chart_png(store: ChatService, agent_id: uuid.UUID) -> tuple[bool, str]:
    text = (
        "Plot these quarterly figures as a bar chart: Q1 120, Q2 150, Q3 90, Q4 210. "
        "Produce the chart image."
    )
    tools, _answer, produced = await _chat(store, agent_id, text)
    pngs = sum(1 for b in produced if b[:4] == b"\x89PNG")
    return pngs > 0, f"tools={tools or 'none'}; png images produced={pngs}"


async def _attached_doc(store: ChatService, agent_id: uuid.UUID) -> tuple[bool, str]:
    token = "RESET-CODE-8842"  # noqa: S105 - a proof fixture string, not a credential
    doc = f"# Site access\n\nThe badge reset code for the north gate is {token}.\n"
    fid = _attach(store, doc.encode(), "access-note.md", "text/markdown")
    text = "Read the attached access note and quote the badge reset code for the north gate."
    tools, answer, _ = await _chat(store, agent_id, text, attachments=[fid])
    return token in answer, f"tools={tools or 'none'}; code quoted={token in answer}"


async def _attached_ocr(store: ChatService, agent_id: uuid.UUID) -> tuple[bool, str]:
    png = _FIXTURES / "ocr-canary.png"
    if not png.exists():
        return False, f"fixture missing: {png}"
    fid = _attach(store, png.read_bytes(), "scan.png", "image/png")
    text = "A scanned image is attached. Read the text in it and tell me the code it shows."
    tools, answer, _ = await _chat(store, agent_id, text, attachments=[fid])
    flat = answer.upper().replace(" ", "")
    return "4821" in flat, f"tools={tools or 'none'}; code read={'4821' in flat}"


async def run() -> int:
    store = demo_store()
    key, url, model = live_settings()
    install_live(store, demo_id("tenant"), key=key, base_url=url, model=model)
    agent_id = _agent(store)

    tasks = [
        ("build a spreadsheet, report the total", _spreadsheet_total),
        ("create a PDF with a marker, read it back", _pdf_marker),
        ("plot figures as a chart", _chart_png),
        ("quote from an attached document", _attached_doc),
        ("OCR an attached scan", _attached_ocr),
    ]
    results: list[tuple[str, bool, str]] = []
    for name, fn in tasks:
        try:
            ok, note = await fn(store, agent_id)
        except Exception as exc:  # noqa: BLE001 - a crash is a failed task, recorded
            ok, note = False, f"raised {type(exc).__name__}: {exc}"
        results.append((name, ok, note))
        print(f"  [{'PASS' if ok else 'FAIL'}] {name} — {note}")

    passed = sum(1 for _, ok, _ in results if ok)
    _scorecard(results, model, passed)
    print(f"\ndocument agent proof: {passed}/{len(results)} tasks passed (model {model})")
    return 0 if passed == len(results) else 1


def _scorecard(results: list[tuple[str, bool, str]], model: str, passed: int) -> None:
    out = Path("docs/testing/document-agent/live-scorecard.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Document agent proof — live scorecard",
        "",
        f"Model: `{model}`. {passed}/{len(results)} tasks passed. "
        "Generated by `scripts/document_agent_proof.py`; gitignored (carries live output).",
        "",
        "| task | result | note |",
        "|---|---|---|",
    ]
    lines.extend(f"| {n} | {'pass' if ok else 'fail'} | {note} |" for n, ok, note in results)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))

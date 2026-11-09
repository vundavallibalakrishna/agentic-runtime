#!/usr/bin/env python
"""Prove the LLM-backed document operations work with a real model.

The toolchain proof (scripts/document_toolchain.py) covers the deterministic document tools;
the agent proof (scripts/document_agent_proof.py) covers the chat flow. This covers the tools
that call a model themselves — `documents.summarise`, `documents.extract`, `documents.compare`
and `image.ask` — by driving each directly through the real `ToolPipeline` with the cert model
(the `reasoning` alias) and a real vision model (the `vision` alias), and asserting the
grounded output: the planted figure is summarised, the fields are extracted, the changed
clause is found, and the vision model reads a value from an image.

It installs a vision-capable model as the `vision` alias (the cert reasoning model cannot see
images). Run:

  AR_EVAL_GYM_LIVE=1 AR_CERT_LLM_API_KEY=... uv run python scripts/document_grounded_proof.py

The cert key is read from the environment and never printed.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any  # noqa: TC003 - used at runtime in function annotations

from ar_domain.chat.service import demo_id
from ar_domain.evals.gym.live import install_live, live_settings
from ar_domain.tools.pipeline import ToolPipeline
from ar_testing.demo import demo_store

# A current, OpenAI-compatible DeepInfra vision-language model, consistent with the cert
# Qwen family. Overridable with AR_CERT_VISION_MODEL.
VISION_MODEL = os.environ.get("AR_CERT_VISION_MODEL", "Qwen/Qwen3-VL-30B-A3B-Instruct")
_FIXTURES = Path("docs/testing/fixtures/m33b")


def install_vision(
    store: Any, tenant_id: uuid.UUID, *, key: str, base_url: str, model: str
) -> None:
    """Point the tenant `vision` alias at a vision-capable OpenAI-compatible model."""
    provider_id, model_id, alias_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    store.providers[provider_id] = {
        "id": provider_id,
        "tenant_id": tenant_id,
        "kind": "openai",
        "name": "Vision live",
        "base_url": base_url.rstrip("/"),
        "api_key": key,
        "timeout_s": 120,
        "status": "active",
    }
    store.models[model_id] = {
        "id": model_id,
        "tenant_id": tenant_id,
        "provider_id": provider_id,
        "upstream_model": model,
        "name": model,
        "capabilities": ["vision"],  # image.ask requires this on the alias's model
    }
    store.aliases[alias_id] = {
        "id": alias_id,
        "tenant_id": tenant_id,
        "alias": "vision",
        "status": "active",
        "primary_model_id": model_id,
    }


class Harness:
    def __init__(self) -> None:
        self.store = demo_store()
        self.pipeline = ToolPipeline(self.store)
        self.tenant = demo_id("tenant")
        self.user = demo_id("admin")
        self.by_name: dict[str, uuid.UUID] = {
            str(row["qualified_name"]): row["id"]
            for row in self.store.tool_versions.values()
            if row.get("qualified_name")
        }

    def call(self, qualified: str, arguments: dict[str, object]) -> dict[str, object]:
        return self.pipeline.execute(
            {
                "tenant_id": self.tenant,
                "user_id": self.user,
                "run_id": uuid.uuid4(),
                "synthetic": True,
                "tool_version_id": self.by_name[qualified],
                "arguments": arguments,
                "model_call_id": f"grounded-{qualified}",
            }
        )

    def upload(self, data: bytes, name: str, media: str) -> uuid.UUID:
        row = self.store.upload(self.tenant, self.user, name, media, data)
        return uuid.UUID(str(row["id"]))

    def ingest(self, data: bytes, name: str, media: str) -> str:
        file_id = self.upload(data, name, media)
        result = self.call("documents.ingest", {"fileId": str(file_id)})
        pres = _pres(result)
        doc = pres.get("document")
        if not isinstance(doc, dict) or not doc.get("id"):
            raise AssertionError(f"ingest failed: {_text(result)[:120]}")
        return str(doc["id"])


def _pres(result: dict[str, object]) -> dict[str, object]:
    structured = result.get("structured")
    pres = structured.get("presentation") if isinstance(structured, dict) else None
    return pres if isinstance(pres, dict) else {}


def _text(result: dict[str, object]) -> str:
    return str(result.get("wrapped") or result.get("result_preview") or "")


def _ok(result: dict[str, object]) -> bool:
    return result.get("status") == "succeeded" and not result.get("is_error")


# --- checks -------------------------------------------------------------------------------
def _summarise(h: Harness) -> tuple[bool, str]:
    doc = (
        "# FY Report\n\nQ3 revenue reached 42 million euros, up from 30 million in Q2. "
        "The CFO is Dana Lin. Headcount held flat at 1,180.\n"
    )
    doc_id = h.ingest(doc.encode(), "fy-report.md", "text/markdown")
    r = h.call("documents.summarise", {"documentId": doc_id, "modelAlias": "reasoning"})
    body = _text(r)
    return (
        _ok(r) and "42" in body
    ), f"ok={_ok(r)}; figure in summary={'42' in body}; {body[:80]!r}"


def _extract(h: Harness) -> tuple[bool, str]:
    doc = (
        "# Invoice\n\nInvoice number: INV-7788\nTotal due: 4281.50 USD\n"
        "Due date: 2026-02-15\nVendor: Acme Supplies\n"
    )
    doc_id = h.ingest(doc.encode(), "invoice.md", "text/markdown")
    r = h.call(
        "documents.extract",
        {"documentId": doc_id, "fields": ["total due", "due date"], "modelAlias": "reasoning"},
    )
    body = _text(r).replace(",", "")
    hit = "4281" in body and "2026-02-15" in body
    return (_ok(r) and hit), f"ok={_ok(r)}; total+date extracted={hit}; {body[:90]!r}"


def _compare(h: Harness) -> tuple[bool, str]:
    a = "# Policy v1\n\nThe data retention period is 7 years for all records.\n"
    b = "# Policy v2\n\nThe data retention period is 10 years for all records.\n"
    a_id = h.ingest(a.encode(), "policy-v1.md", "text/markdown")
    b_id = h.ingest(b.encode(), "policy-v2.md", "text/markdown")
    r = h.call(
        "documents.compare",
        {"documentId": a_id, "otherDocumentId": b_id, "modelAlias": "reasoning"},
    )
    body = _text(r)
    hit = "10" in body and "7" in body
    return (_ok(r) and hit), f"ok={_ok(r)}; retention change found={hit}; {body[:90]!r}"


def _image_ask_text(h: Harness) -> tuple[bool, str]:
    png = _FIXTURES / "ocr-canary.png"
    if not png.exists():
        return False, f"fixture missing: {png}"
    file_id = h.upload(png.read_bytes(), "scan.png", "image/png")
    r = h.call(
        "image.ask",
        {
            "fileId": str(file_id),
            "question": "What code is written in this image? Give the digits only.",
        },
    )
    body = _text(r)
    return (
        _ok(r) and "4821" in body
    ), f"ok={_ok(r)}; vision read 4821={'4821' in body}; {body[:80]!r}"


def run() -> int:
    h = Harness()
    key, url, model = live_settings()
    install_live(h.store, h.tenant, key=key, base_url=url, model=model)
    install_vision(h.store, h.tenant, key=key, base_url=url, model=VISION_MODEL)

    checks = [
        ("documents.summarise — grounded summary", _summarise),
        ("documents.extract — field extraction", _extract),
        ("documents.compare — what changed", _compare),
        ("image.ask — read a value from an image", _image_ask_text),
    ]
    results: list[tuple[str, bool, str]] = []
    for name, fn in checks:
        try:
            ok, note = fn(h)
        except Exception as exc:  # noqa: BLE001 - a crash is a failed check, recorded
            ok, note = False, f"raised {type(exc).__name__}: {exc}"[:160]
        results.append((name, ok, note))
        print(f"  [{'PASS' if ok else 'FAIL'}] {name} — {note}")

    passed = sum(1 for _, ok, _ in results if ok)
    _scorecard(results, model, VISION_MODEL, passed)
    print(
        f"\ndocument grounded proof: {passed}/{len(results)} checks passed "
        f"(reasoning {model}, vision {VISION_MODEL})"
    )
    return 0 if passed == len(results) else 1


def _scorecard(results: list[tuple[str, bool, str]], model: str, vision: str, passed: int) -> None:
    out = Path("docs/testing/document-agent/grounded-scorecard.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Document grounded proof — live scorecard",
        "",
        f"Reasoning: `{model}`. Vision: `{vision}`. {passed}/{len(results)} checks passed. "
        "Generated by `scripts/document_grounded_proof.py`; gitignored (carries live output).",
        "",
        "| check | result | note |",
        "|---|---|---|",
    ]
    lines.extend(f"| {n} | {'pass' if ok else 'fail'} | {note} |" for n, ok, note in results)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(run())

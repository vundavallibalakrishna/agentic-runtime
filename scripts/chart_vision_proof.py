#!/usr/bin/env python
"""Stress-test chart legibility: render hard charts and have a vision model read them.

The chart fidelity fix (#148) labels charts so a vision model can read them. This pushes
harder — many bars, long labels, negatives, decimals, large magnitudes, line/pie/scatter,
and a wide value range — and for each asks the real vision model a factual question, checking
the answer. Failures are legibility gaps to fix.

  AR_EVAL_GYM_LIVE=1 AR_CERT_LLM_API_KEY=... uv run python scripts/chart_vision_proof.py

The cert key is read from the environment and never printed.
"""

from __future__ import annotations

import os
import uuid
from typing import Any  # noqa: TC003 - runtime use in annotations

from ar_domain.chat.service import demo_id
from ar_domain.evals.gym.live import install_live, live_settings
from ar_domain.tools.pipeline import ToolPipeline
from ar_testing.demo import demo_store

VISION_MODEL = os.environ.get("AR_CERT_VISION_MODEL", "Qwen/Qwen3-VL-30B-A3B-Instruct")


def install_vision(store: Any, tenant: uuid.UUID, key: str, url: str, model: str) -> None:
    p, m, a = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    store.providers[p] = {
        "id": p,
        "tenant_id": tenant,
        "kind": "openai",
        "name": "V",
        "base_url": url.rstrip("/"),
        "api_key": key,
        "timeout_s": 120,
        "status": "active",
    }
    store.models[m] = {
        "id": m,
        "tenant_id": tenant,
        "provider_id": p,
        "upstream_model": model,
        "name": model,
        "capabilities": ["vision"],
    }
    store.aliases[a] = {
        "id": a,
        "tenant_id": tenant,
        "alias": "vision",
        "status": "active",
        "primary_model_id": m,
    }


class Judge:
    def __init__(self) -> None:
        self.store = demo_store()
        self.tenant, self.user = demo_id("tenant"), demo_id("admin")
        key, url, model = live_settings()
        install_live(self.store, self.tenant, key=key, base_url=url, model=model)
        install_vision(self.store, self.tenant, key, url, VISION_MODEL)
        self.by = {
            str(r["qualified_name"]): r["id"]
            for r in self.store.tool_versions.values()
            if r.get("qualified_name")
        }

    def _call(self, qualified: str, args: dict[str, object]) -> dict[str, object]:
        return ToolPipeline(self.store).execute(
            {
                "tenant_id": self.tenant,
                "user_id": self.user,
                "run_id": uuid.uuid4(),
                "synthetic": True,
                "tool_version_id": self.by[qualified],
                "arguments": args,
                "model_call_id": "c",
            }
        )

    def ask(self, chart_args: dict[str, object], question: str) -> str:
        chart = self._call("general.chart", chart_args)
        structured = chart.get("structured")
        presentation = structured.get("presentation") if isinstance(structured, dict) else None
        files = presentation.get("files") if isinstance(presentation, dict) else None
        if not isinstance(files, list) or not files:
            return f"[chart failed: {chart.get('text')}]"
        blob = self.store.blobs[uuid.UUID(str(files[0]["file_id"]))]
        up = self.store.upload(self.tenant, self.user, "chart.png", "image/png", blob)
        r = self._call("image.ask", {"fileId": str(up["id"]), "question": question})
        text = str(r.get("wrapped") or r.get("result_preview") or "")
        body = text.rsplit("nonce=", maxsplit=1)[-1].split(">", 1)[-1]
        return body.replace("</tool_result>", "").strip()


def _months() -> list[dict[str, object]]:
    vals = [31, 28, 44, 39, 52, 61, 58, 70, 49, 37, 25, 33]  # Aug (index 7) = 70 is the max
    names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    return [{"m": n, "v": v} for n, v in zip(names, vals, strict=True)]


CASES: list[tuple[str, dict[str, object], str, list[str]]] = [
    (
        "12 bars — find the max month",
        {"kind": "bar", "title": "Monthly Signups", "xKey": "m", "yKey": "v", "rows": _months()},
        "Which month has the tallest bar? Answer with the month abbreviation only.",
        ["aug"],
    ),
    (
        "long category labels",
        {
            "kind": "bar",
            "title": "Headcount by Team",
            "xKey": "team",
            "yKey": "n",
            "rows": [
                {"team": "Engineering", "n": 120},
                {"team": "Marketing", "n": 45},
                {"team": "Operations", "n": 78},
                {"team": "Finance", "n": 33},
            ],
        },
        "Which team has the most headcount, and what is the value? Answer briefly.",
        ["120", "engineer"],
    ),
    (
        "decimal values — read one",
        {
            "kind": "bar",
            "title": "Avg Rating",
            "xKey": "p",
            "yKey": "r",
            "rows": [{"p": "AppA", "r": 3.5}, {"p": "AppB", "r": 4.7}, {"p": "AppC", "r": 2.9}],
        },
        "What is the rating value of the tallest bar? Give the number.",
        ["4.7"],
    ),
    (
        "large magnitudes (thousands)",
        {
            "kind": "bar",
            "title": "Revenue USD",
            "xKey": "q",
            "yKey": "usd",
            "rows": [
                {"q": "Q1", "usd": 12000},
                {"q": "Q2", "usd": 8500},
                {"q": "Q3", "usd": 23000},
                {"q": "Q4", "usd": 15500},
            ],
        },
        "What is the value of the tallest bar? Read it exactly as labelled.",
        ["23k", "23000", "23,000"],
    ),
    (
        "wide range — read a small bar's value",
        {
            "kind": "bar",
            "title": "Errors by Service",
            "xKey": "s",
            "yKey": "e",
            "rows": [
                {"s": "Auth", "e": 1000},
                {"s": "Cart", "e": 8},
                {"s": "Search", "e": 15},
                {"s": "Pay", "e": 4},
            ],
        },
        "What is the value shown for the 'Pay' bar? Give the number.",
        ["4"],
    ),
    (
        "line chart — find the peak point",
        {
            "kind": "line",
            "title": "Weekly Active Users",
            "xKey": "w",
            "yKey": "u",
            "rows": [
                {"w": "W1", "u": 40},
                {"w": "W2", "u": 65},
                {"w": "W3", "u": 120},
                {"w": "W4", "u": 90},
                {"w": "W5", "u": 75},
            ],
        },
        "At which week does the line reach its highest point? Answer with the week label.",
        ["w3", "week 3"],
    ),
    (
        "pie chart — largest slice",
        {
            "kind": "pie",
            "title": "Traffic Source",
            "xKey": "src",
            "yKey": "pct",
            "rows": [
                {"src": "Organic", "pct": 50},
                {"src": "Paid", "pct": 20},
                {"src": "Social", "pct": 20},
                {"src": "Email", "pct": 10},
            ],
        },
        "Which is the largest traffic source, and what percentage? Answer briefly.",
        ["organic", "50"],
    ),
    (
        "negative values — find the loss",
        {
            "kind": "bar",
            "title": "Profit by Quarter",
            "xKey": "q",
            "yKey": "p",
            "rows": [
                {"q": "Q1", "p": 30},
                {"q": "Q2", "p": -15},
                {"q": "Q3", "p": 20},
                {"q": "Q4", "p": 45},
            ],
        },
        "Which quarter shows a negative value (a loss)? Answer with the quarter label.",
        ["q2"],
    ),
    (
        "grouped bars — read the tallest bar value",
        {
            "kind": "grouped",
            "title": "Sales by Line",
            "xKey": "quarter",
            "rows": [
                {"quarter": "Q1", "Widgets": 30, "Gadgets": 12},
                {"quarter": "Q2", "Widgets": 18, "Gadgets": 40},
                {"quarter": "Q3", "Widgets": 25, "Gadgets": 22},
            ],
        },
        "This grouped bar chart's bars are labelled with their values. What is the value of "
        "the single tallest bar? Give the number.",
        ["40"],
    ),
    (
        "grouped bars — read the legend",
        {
            "kind": "grouped",
            "title": "Sales by Line",
            "xKey": "quarter",
            "rows": [
                {"quarter": "Q1", "Widgets": 30, "Gadgets": 12},
                {"quarter": "Q2", "Widgets": 18, "Gadgets": 40},
            ],
        },
        "The legend names the two series. One is 'Widgets'. What is the other series called?",
        ["gadgets"],
    ),
    (
        "stacked bars — tallest total",
        {
            "kind": "stacked",
            "title": "Sales by Line",
            "xKey": "quarter",
            "rows": [
                {"quarter": "Q1", "Widgets": 30, "Gadgets": 12},
                {"quarter": "Q2", "Widgets": 18, "Gadgets": 40},
                {"quarter": "Q3", "Widgets": 25, "Gadgets": 22},
            ],
        },
        "In this stacked bar chart, which quarter has the tallest total stack? Answer with "
        "the quarter label.",
        ["q2"],
    ),
    (
        "stacked bars — read the total label",
        {
            "kind": "stacked",
            "title": "Sales by Line",
            "xKey": "quarter",
            "rows": [
                {"quarter": "Q1", "Widgets": 30, "Gadgets": 12},
                {"quarter": "Q2", "Widgets": 18, "Gadgets": 40},
                {"quarter": "Q3", "Widgets": 25, "Gadgets": 22},
            ],
        },
        "Each stacked bar has its total printed above it. What is the total printed above "
        "the Q2 bar? Give the number.",
        ["58"],
    ),
    (
        "multiline — read a labelled point value",
        {
            "kind": "multiline",
            "title": "Sales vs Costs",
            "xKey": "month",
            "rows": [
                {"month": "Jan", "Sales": 10, "Costs": 4},
                {"month": "Feb", "Sales": 14, "Costs": 6},
                {"month": "Mar", "Sales": 9, "Costs": 12},
            ],
        },
        "This chart has two lines, Sales and Costs (see the legend); each point is labelled "
        "with its value. What is the value of the Costs line in March? Give the number.",
        ["12"],
    ),
    (
        "grouped — many categories, tallest bar",
        {
            "kind": "grouped",
            "title": "Units by Region",
            "xKey": "region",
            "rows": [
                {"region": "North", "Y2023": 20, "Y2024": 28},
                {"region": "South", "Y2023": 35, "Y2024": 30},
                {"region": "East", "Y2023": 18, "Y2024": 90},
                {"region": "West", "Y2023": 40, "Y2024": 25},
                {"region": "Central", "Y2023": 22, "Y2024": 33},
                {"region": "Coast", "Y2023": 15, "Y2024": 27},
            ],
        },
        "This grouped bar chart has six regions and two years. Which region has the single "
        "tallest bar? Answer with the region name.",
        ["east"],
    ),
    (
        "stacked — five series, tallest total",
        {
            "kind": "stacked",
            "title": "Spend by Team",
            "xKey": "quarter",
            "rows": [
                {"quarter": "Q1", "Eng": 10, "Sales": 8, "Ops": 6, "Mkt": 4, "HR": 2},
                {"quarter": "Q2", "Eng": 20, "Sales": 18, "Ops": 15, "Mkt": 12, "HR": 9},
                {"quarter": "Q3", "Eng": 12, "Sales": 9, "Ops": 7, "Mkt": 5, "HR": 3},
            ],
        },
        "In this stacked chart with five teams, which quarter has the tallest total stack? "
        "Answer with the quarter label.",
        ["q2"],
    ),
    (
        "grouped — a negative series",
        {
            "kind": "grouped",
            "title": "Revenue and Adjustments",
            "xKey": "quarter",
            "rows": [
                {"quarter": "Q1", "Revenue": 30, "Adjustment": -12},
                {"quarter": "Q2", "Revenue": 45, "Adjustment": -8},
                {"quarter": "Q3", "Revenue": 38, "Adjustment": -15},
            ],
        },
        "One series in this grouped chart has bars that drop below the zero line (negative "
        "values). Which series is it? Answer with the series name.",
        ["adjustment"],
    ),
    (
        "stacked100 — read a segment percentage",
        {
            "kind": "stacked100",
            "title": "Share by Product",
            "xKey": "quarter",
            "rows": [
                {"quarter": "Q1", "A": 30, "B": 10, "C": 10},
                {"quarter": "Q2", "A": 20, "B": 20, "C": 20},
                {"quarter": "Q3", "A": 5, "B": 5, "C": 40},
            ],
        },
        "This is a 100% stacked chart; each segment is labelled with its percentage. In the "
        "Q3 bar, what percentage is the largest segment? Give the percentage.",
        ["80"],
    ),
    (
        "dual axis — identify the right-axis series",
        {
            "kind": "dual",
            "title": "Revenue and Growth",
            "xKey": "quarter",
            "rightKeys": ["Growth"],
            "rows": [
                {"quarter": "Q1", "Revenue": 1200, "Growth": 5},
                {"quarter": "Q2", "Revenue": 1800, "Growth": 12},
                {"quarter": "Q3", "Revenue": 1500, "Growth": 8},
            ],
        },
        "This dual-axis chart has bars on the left axis and a line on the right axis. The "
        "legend marks the right-axis series with '(R)'. What is that series called?",
        ["growth"],
    ),
]


def run() -> int:
    judge = Judge()
    results: list[tuple[str, bool, str]] = []
    for name, chart_args, question, expected in CASES:
        try:
            answer = judge.ask(chart_args, question)
            low = answer.lower()
            ok = any(e.lower() in low for e in expected)
        except Exception as exc:  # noqa: BLE001 - a crash is a failed case, recorded
            ok, answer = False, f"raised {type(exc).__name__}: {exc}"[:160]
        results.append((name, ok, answer[:140]))
        print(
            f"  [{'PASS' if ok else 'FAIL'}] {name}\n        expect~{expected} :: {answer[:120]!r}"
        )
    passed = sum(1 for _, ok, _ in results if ok)
    print(f"\nchart vision proof: {passed}/{len(results)} (vision {VISION_MODEL})")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(run())

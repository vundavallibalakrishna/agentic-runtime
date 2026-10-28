"""Golden suites for the evidence collector and the control tester.

A case that omits the evidence hash fails, and the suite gates template publish.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from ar_domain.evals.book import EvalBook
from ar_domain.evals.runner import execute_eval_run

if TYPE_CHECKING:
    from ar_domain.agents.access import Actor

ROOT = Path(__file__).resolve().parents[2] / "evals"


def documents() -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for path in sorted(ROOT.glob("*/*.yaml")):
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            found.append({str(key): value for key, value in loaded.items()})
    return found


def install_suites(store: Any, actor: Actor, agent_id: uuid.UUID | None = None) -> int:
    book = EvalBook(store)
    created = 0
    for document in documents():
        name = str(document.get("name") or "")
        if not name or _named(store, actor, name):
            continue
        suite = book.create_suite(
            actor,
            {
                "name": name,
                "description": str(document.get("description") or ""),
                "kind": str(document.get("kind") or "functional"),
                "agent_id": None if agent_id is None else str(agent_id),
                "gate": document.get("gate") or {"required": True},
            },
        )
        suite_id = suite["id"]
        cases = document.get("cases")
        if isinstance(cases, list) and isinstance(suite_id, uuid.UUID):
            for case in cases:
                if isinstance(case, dict):
                    book.create_case(actor, suite_id, case)
        created += 1
    return created


def run_suites(store: Any, actor: Actor, agent_id: uuid.UUID | None = None) -> list[dict[str, Any]]:
    """Score every pack suite. A missing evidence hash fails the gate."""
    install_suites(store, actor, agent_id)
    book = EvalBook(store)
    summaries: list[dict[str, Any]] = []
    for suite in book.list_suites(actor):
        if not str(suite.get("name") or "").startswith("GRC "):
            continue
        suite_id = suite.get("id")
        if not isinstance(suite_id, uuid.UUID):
            continue
        started = book.start_run(actor, suite_id, {"agent_version_ref": "published"})
        run_id = started.get("id")
        if isinstance(run_id, uuid.UUID) and getattr(store, "defer_eval_runs", False):
            execute_eval_run(store, run_id)
        if isinstance(run_id, uuid.UUID):
            enforce_evidence_hash(store, run_id)
            summary = store.eval_runs[run_id].get("summary")
            if isinstance(summary, dict):
                summaries.append(summary)
    return summaries


def hashes_present(case: dict[str, Any]) -> bool:
    mocks = case.get("tool_mocks")
    if not isinstance(mocks, list) or not mocks:
        return False
    for mock in mocks:
        if not isinstance(mock, dict):
            return False
        result = mock.get("result")
        if not isinstance(result, dict) or not str(result.get("evidenceHash") or ""):
            return False
    return True


def enforce_evidence_hash(store: Any, eval_run_id: uuid.UUID) -> bool:
    """Fail the run when a scripted tool result omits the evidence hash."""
    run = store.eval_runs.get(eval_run_id)
    if not isinstance(run, dict):
        return False
    suite_id = run.get("suite_id")
    omitted = False
    for case in store.eval_cases.values():
        if not isinstance(case, dict) or case.get("suite_id") != suite_id:
            continue
        if hashes_present(case):
            continue
        omitted = True
        for result in store.eval_results.values():
            if not isinstance(result, dict):
                continue
            if result.get("eval_run_id") != eval_run_id or result.get("case_id") != case.get("id"):
                continue
            result["passed"] = False
            scores = result.get("scores")
            if isinstance(scores, dict):
                scores["evidence_hash"] = {"passed": False, "score": 0.0, "detail": "omitted"}
    summary = run.get("summary")
    if omitted and isinstance(summary, dict):
        summary["gate_passed"] = False
        summary["pass_rate"] = 0.0
    return not omitted


def _named(store: Any, actor: Actor, name: str) -> bool:
    for row in store.eval_suites.values():
        if row.get("tenant_id") == actor.tenant_id and row.get("name") == name:
            return True
    return False

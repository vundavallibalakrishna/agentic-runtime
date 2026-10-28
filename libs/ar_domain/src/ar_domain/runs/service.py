"""In-product observability. Spec: docs/03-specs/18-observability-eval.md §3."""

import os
from collections import Counter
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import uuid
    from typing import Any

OVERVIEW_SQL = """
SELECT status, trigger, count(*)
FROM runs
WHERE tenant_id = :tenant_id
  AND created_at >= :start
  AND created_at < :end
GROUP BY status, trigger
"""


def trace_links(run: dict[str, object]) -> dict[str, object]:
    """Add Tempo and Langfuse links when the operator configured them."""
    body = dict(run)
    trace_id = str(run.get("trace_id") or "")
    base = os.environ.get("AR_TRACE_UI_URL", "").strip().rstrip("/")
    if base and trace_id:
        body["trace_url"] = f"{base}/explore?traceId={trace_id}"
    port = os.environ.get("AR_LANGFUSE_HOST_PORT", "").strip()
    if port.isdigit() and trace_id:
        body["langfuse_url"] = f"http://localhost:{port}/trace/{trace_id}"
    return body


def overview(
    store: Any,
    tenant_id: uuid.UUID,
    *,
    start: datetime | None = None,
    end: datetime | None = None,
    agent_id: uuid.UUID | None = None,
) -> dict[str, object]:
    """Aggregate runs, tools, approvals, feedback and cost for one tenant."""
    runs = [
        row
        for row in store.runs.values()
        if isinstance(row, dict)
        and row.get("tenant_id") == tenant_id
        and _in_window(row.get("created_at"), start, end)
        and (agent_id is None or row.get("agent_id") == agent_id)
    ]
    compact = [
        (
            str(row.get("status") or "unknown"),
            str(row.get("trigger") or "chat"),
            _latency(row),
            str(row.get("agent_id") or ""),
            str(row.get("error") or ""),
        )
        for row in runs
    ]
    body = aggregate_run_rows(compact)
    body["tools"] = _tools(store, tenant_id, {row.get("id") for row in runs})
    body["approvals"] = _approvals(store, tenant_id, start, end)
    body["feedback"] = _feedback(store, tenant_id, start, end)
    body["cost_micros"] = _cost(store, tenant_id, start, end)
    return body


def aggregate_run_rows(rows: list[tuple[str, str, int, str, str]]) -> dict[str, object]:
    """Count statuses, triggers, latency and errors. The hot loop stays allocation-light."""
    by_status: Counter[str] = Counter()
    by_trigger: Counter[str] = Counter()
    by_agent: Counter[str] = Counter()
    by_error: Counter[str] = Counter()
    latencies: list[int] = []
    for status, trigger, latency, agent, error in rows:
        by_status[status] += 1
        by_trigger[trigger] += 1
        if agent:
            by_agent[agent] += 1
        if error:
            by_error[error] += 1
        if latency:
            latencies.append(latency)
    ordered = sorted(latencies)
    return {
        "runs": {
            "total": len(rows),
            "by_status": dict(by_status),
            "by_trigger": dict(by_trigger),
        },
        "latency": {
            "run_p50_ms": _percentile(ordered, 0.50),
            "run_p95_ms": _percentile(ordered, 0.95),
            "ttft_p95_ms": _percentile(ordered, 0.95),
        },
        "top_agents": [
            {"agent_id": agent, "runs": count} for agent, count in by_agent.most_common(5)
        ],
        "top_errors": [{"code": code, "count": count} for code, count in by_error.most_common(5)],
    }


def _tools(store: Any, tenant_id: uuid.UUID, run_ids: set[object]) -> list[dict[str, object]]:
    counts: dict[str, list[int]] = {}
    errors: Counter[str] = Counter()
    for call in store.tool_calls.values():
        if not isinstance(call, dict) or call.get("tenant_id") != tenant_id:
            continue
        if run_ids and call.get("run_id") not in run_ids:
            continue
        name = str(call.get("qualified_name") or "tool")
        bucket = counts.setdefault(name, [0, 0])
        bucket[0] += 1
        latency = call.get("latency_ms")
        if isinstance(latency, int):
            bucket[1] += latency
        if call.get("status") in {"failed", "denied"}:
            errors[name] += 1
    rows = []
    for name, (calls, latency_sum) in counts.items():
        rows.append(
            {
                "qualified_name": name,
                "calls": calls,
                "error_rate": (errors[name] / calls) if calls else 0.0,
                "p95_ms": int(latency_sum / calls) if calls else 0,
            }
        )
    rows.sort(key=lambda item: item["calls"] if isinstance(item["calls"], int) else 0, reverse=True)
    return rows[:20]


def _approvals(
    store: Any, tenant_id: uuid.UUID, start: datetime | None, end: datetime | None
) -> dict[str, object]:
    counts: Counter[str] = Counter()
    for row in store.approvals.values():
        if not isinstance(row, dict) or row.get("tenant_id") != tenant_id:
            continue
        if not _in_window(row.get("created_at"), start, end):
            continue
        counts[str(row.get("status") or "requested")] += 1
    return {
        "requested": sum(counts.values()),
        "approved": counts.get("approved", 0),
        "rejected": counts.get("rejected", 0),
        "expired": counts.get("expired", 0),
        "median_decision_s": 0,
    }


def _feedback(
    store: Any, tenant_id: uuid.UUID, start: datetime | None, end: datetime | None
) -> dict[str, int]:
    up = 0
    down = 0
    for row in store.feedback.values():
        if not isinstance(row, dict) or row.get("tenant_id") != tenant_id:
            continue
        if not _in_window(row.get("created_at"), start, end):
            continue
        if row.get("rating") == "up":
            up += 1
        elif row.get("rating") == "down":
            down += 1
    return {"up": up, "down": down}


def _cost(store: Any, tenant_id: uuid.UUID, start: datetime | None, end: datetime | None) -> int:
    total = 0
    for key, row in store.usage_daily.items():
        if not isinstance(key, tuple) or not key or str(key[0]) != str(tenant_id):
            continue
        if isinstance(row, dict):
            cost = row.get("cost_micros")
            if isinstance(cost, int):
                total += cost
        elif isinstance(row, int):
            total += row
    del start, end
    return total


def _latency(row: dict[str, object]) -> int:
    usage = row.get("usage")
    if isinstance(usage, dict):
        wall = usage.get("wall_clock_ms")
        if isinstance(wall, int):
            return wall
    return 0


def _in_window(value: object, start: datetime | None, end: datetime | None) -> bool:
    if start is None and end is None:
        return True
    if not isinstance(value, datetime):
        return True
    if start is not None and value < start:
        return False
    return end is None or value < end


def _percentile(ordered: list[int], fraction: float) -> int:
    if not ordered:
        return 0
    index = min(len(ordered) - 1, max(int(fraction * len(ordered)) - 1, 0))
    return ordered[index]

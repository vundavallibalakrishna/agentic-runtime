"""Usage summaries and chargeback CSV.

Spec: docs/03-specs/17-audit-usage-metering.md §2.4.
"""

import csv
from io import StringIO

_GROUPS = {
    "day": "day",
    "metric": "metric",
    "agent": "agent",
    "user": "user",
    "team": "team",
    "model": "model",
    "model_alias": "model",
    "tenant": "tenant",
}


def normalise_groups(raw: str) -> tuple[str, ...]:
    """At most two group names. Empty means day."""
    parts = [part.strip() for part in raw.split(",") if part.strip()]
    if not parts:
        return ("day",)
    if len(parts) > 2 or any(part not in _GROUPS for part in parts):
        raise ValueError(raw)
    return tuple(_GROUPS[part] for part in parts)


def aggregate(rows: list[dict[str, object]], groups: tuple[str, ...]) -> list[dict[str, object]]:
    """Sum quantity and cost for the requested keys."""
    totals: dict[tuple[str, ...], list[int]] = {}
    labels: dict[tuple[str, ...], dict[str, str]] = {}
    for row in rows:
        key = tuple(str(row.get(name) or "") for name in groups)
        bucket = totals.setdefault(key, [0, 0])
        bucket[0] += _count(row.get("quantity"))
        bucket[1] += _count(row.get("cost_micros"))
        labels[key] = {name: str(row.get(name) or "") for name in groups}
    found = [
        {"keys": labels[key], "quantity": values[0], "cost_micros": values[1]}
        for key, values in totals.items()
    ]
    found.sort(key=lambda item: _key_tuple(item, groups))
    return found


def _key_tuple(item: dict[str, object], groups: tuple[str, ...]) -> tuple[str, ...]:
    keys = item.get("keys")
    if not isinstance(keys, dict):
        return tuple("" for _ in groups)
    return tuple(str(keys.get(name, "")) for name in groups)


def sum_rows(rows: list[dict[str, object]]) -> dict[str, int]:
    """Totals across a summary."""
    quantity = sum(_count(row.get("quantity")) for row in rows)
    cost = sum(_count(row.get("cost_micros")) for row in rows)
    return {"quantity": quantity, "cost_micros": cost}


def _count(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return value


def usage_csv(rows: list[dict[str, object]], currency: str) -> str:
    """UTF-8 chargeback file. Columns match spec 17 §2.4."""
    header = [
        "day",
        "metric",
        "user_email",
        "team",
        "agent_slug",
        "model_alias",
        "quantity",
        "cost_micros",
        "currency",
    ]
    ordered = sorted(
        rows,
        key=lambda row: (str(row.get("day")), str(row.get("metric")), str(row.get("user_email"))),
    )
    return _write(header, ordered, currency, extra=())


def platform_csv(rows: list[dict[str, object]], currency: str) -> str:
    """Per tenant, day and metric, with the plan key."""
    header = [
        "tenant_id",
        "day",
        "metric",
        "quantity",
        "cost_micros",
        "currency",
        "plan_key",
    ]
    ordered = sorted(
        rows,
        key=lambda row: (str(row.get("tenant_id")), str(row.get("day")), str(row.get("metric"))),
    )
    return _write(header, ordered, currency, extra=("tenant_id", "plan_key"))


def _write(
    header: list[str],
    rows: list[dict[str, object]],
    currency: str,
    *,
    extra: tuple[str, ...],
) -> str:
    buffer = StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(header)
    for row in rows:
        values: list[object] = []
        for column in header:
            if column == "currency":
                values.append(currency)
            elif column in extra or column in {
                "day",
                "metric",
                "user_email",
                "team",
                "agent_slug",
                "model_alias",
                "quantity",
                "cost_micros",
            }:
                values.append(row.get(column, ""))
            else:
                values.append(row.get(column, ""))
        writer.writerow(values)
    return buffer.getvalue()

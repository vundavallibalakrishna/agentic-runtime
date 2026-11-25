"""Per-field comparison for an eval case.

Normalisers are named on the assertion. They are not chosen by looking at the
words of a document.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime

import orjson


def fields_match(item: dict[str, object], outcome: dict[str, object]) -> dict[str, object]:
    """Precision, recall and a per-field breakdown against ``expected``."""
    expected = item.get("expected")
    if not isinstance(expected, dict):
        return _score(False, 0.0, "expected object missing", [])
    predicted = _predicted(outcome)
    normalisers = item.get("normalisers")
    named = normalisers if isinstance(normalisers, dict) else {}
    rows = []
    for path, wanted in _flat(expected):
        got = _get(predicted, path)
        kind = str(named.get(path) or "exact")
        ok = _equal(wanted, got, kind)
        rows.append(
            {
                "path": path,
                "expected": wanted,
                "actual": got,
                "normaliser": kind,
                "match": ok,
                "document_type": str(item.get("document_type") or ""),
            }
        )
    labelled = len(rows)
    correct = sum(1 for row in rows if row["match"] and row["actual"] is not None)
    expected_paths = {path for path, _value in _flat(expected)}
    extra = [path for path, _value in _flat(predicted) if path not in expected_paths]
    rows.extend(
        {
            "path": path,
            "expected": None,
            "actual": _get(predicted, path),
            "normaliser": "extra",
            "match": False,
            "document_type": str(item.get("document_type") or ""),
        }
        for path in extra
    )
    predicted_count = sum(1 for row in rows if row["actual"] is not None)
    precision = correct / predicted_count if predicted_count else 0.0
    recall = correct / labelled if labelled else 0.0
    f1 = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
    passed = labelled > 0 and correct == labelled and not extra
    return {
        "passed": passed,
        "score": f1,
        "reason": "matched" if passed else "field mismatch",
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "fields": rows,
        "document_type": str(item.get("document_type") or ""),
    }


def report(results: list[dict[str, object]]) -> dict[str, object]:
    """Group field rows by path and by document type."""
    by_field: dict[str, list[bool]] = {}
    by_type: dict[str, list[bool]] = {}
    for result in results:
        rows = result.get("fields")
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            path = str(row.get("path") or "")
            kind = str(row.get("document_type") or "")
            by_field.setdefault(path, []).append(bool(row.get("match")))
            by_type.setdefault(kind, []).append(bool(row.get("match")))
    return {
        "by_field": {key: _rate(value) for key, value in by_field.items()},
        "by_document_type": {key: _rate(value) for key, value in by_type.items()},
    }


def _predicted(outcome: dict[str, object]) -> dict[str, object]:
    raw = outcome.get("output_json")
    if isinstance(raw, dict):
        return raw
    text = str(outcome.get("output_text") or "")
    try:
        parsed = orjson.loads(text)
    except orjson.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _flat(value: object, prefix: str = "") -> list[tuple[str, object]]:
    if isinstance(value, dict):
        found: list[tuple[str, object]] = []
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if isinstance(item, dict):
                found.extend(_flat(item, path))
            else:
                found.append((path, item))
        return found
    return [(prefix, value)] if prefix else []


def _get(payload: dict[str, object], path: str) -> object:
    cursor: object = payload
    for part in path.split("."):
        if not isinstance(cursor, dict) or part not in cursor:
            return None
        cursor = cursor[part]
    return cursor


def _equal(expected: object, actual: object, kind: str) -> bool:
    if isinstance(expected, list) or isinstance(actual, list):
        return _lists_match(expected, actual, kind)
    if actual is None:
        return False
    if kind == "number":
        return _number(expected) == _number(actual)
    if kind == "date":
        return _date(expected) == _date(actual) and _date(expected) != ""
    if kind == "name":
        return _name(expected) == _name(actual) and _name(expected) != ""
    return _name(expected) == _name(actual) if kind == "text" else str(expected) == str(actual)


def _lists_match(expected: object, actual: object, kind: str) -> bool:
    """Order does not matter. Each expected item must match one predicted item."""
    if not isinstance(expected, list) or not isinstance(actual, list):
        return False
    if len(expected) != len(actual):
        return False
    pending = list(actual)
    for wanted in expected:
        found = next(
            (
                index
                for index, got in enumerate(pending)
                if _equal(wanted, got, "exact" if kind == "array" else kind)
            ),
            None,
        )
        if found is None:
            return False
        pending.pop(found)
    return True


def _number(value: object) -> str:
    text = re.sub(r"[^0-9.\-]", "", str(value))
    try:
        return f"{float(text):.4f}"
    except ValueError:
        return ""


def _date(value: object) -> str:
    text = str(value).strip()
    for pattern in ("%Y-%m-%d", "%d/%m/%Y", "%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(text, pattern).date().isoformat()  # noqa: DTZ007
        except ValueError:
            continue
    return ""


def _name(value: object) -> str:
    folded = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", folded).strip().casefold()


def _rate(flags: list[bool]) -> dict[str, float]:
    total = len(flags)
    correct = sum(1 for item in flags if item)
    return {"n": float(total), "recall": correct / total if total else 0.0}


def _score(ok: bool, score: float, detail: str, rows: list[object]) -> dict[str, object]:  # noqa: FBT001
    return {
        "passed": ok,
        "score": score,
        "reason": detail,
        "fields": rows,
        "precision": 0.0,
        "recall": 0.0,
        "f1": score,
    }

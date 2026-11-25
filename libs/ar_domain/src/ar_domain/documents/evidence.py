"""Per-field extraction. The model fills values. The code checks the quotes.

A field is extracted only when its quote is in the source and its confidence is
at least the configured threshold. A missing required field is reported, not a
reason to throw away the fields that were found. Long text is split when it
does not fit the model's usable window.
"""

from __future__ import annotations

import hashlib

import orjson
from jsonschema import Draft202012Validator

from ar_common.settings import get_settings
from ar_domain.documents.grounding import _contains
from ar_domain.documents.strategy import estimate_tokens, usable_tokens


def schema_hash(schema: dict[str, object]) -> str:
    return hashlib.sha256(orjson.dumps(schema, option=orjson.OPT_SORT_KEYS)).hexdigest()


def choose_strategy(text: str, context_window: int | None) -> str:
    """``single`` when the text fits the window, otherwise ``map``."""
    window = context_window if isinstance(context_window, int) and context_window > 0 else None
    if window is None:
        window = int(get_settings().default_context_window)
    budget = usable_tokens(window)
    if budget is None:
        return "single"
    return "single" if estimate_tokens(text) <= budget else "map"


def chunks_for(
    passages: list[dict[str, object]], context_window: int | None
) -> list[list[dict[str, object]]]:
    """Groups of passages that each fit the usable window."""
    if choose_strategy(_join(passages), context_window) == "single":
        return [passages] if passages else []
    window = context_window if isinstance(context_window, int) and context_window > 0 else None
    budget = usable_tokens(window or int(get_settings().default_context_window)) or 1
    groups: list[list[dict[str, object]]] = []
    current: list[dict[str, object]] = []
    used = 0
    for item in passages:
        cost = estimate_tokens(str(item.get("text") or ""))
        if current and used + cost > budget:
            groups.append(current)
            current = []
            used = 0
        current.append(item)
        used += cost
    if current:
        groups.append(current)
    return groups


def prompt_for(schema: dict[str, object]) -> str:
    """Ask for one evidence object per leaf. The schema's required list is the contract."""
    return (
        "Fill this JSON Schema from the passages only. "
        "Return one JSON object and no other text, shaped as "
        '{"fields": {"<dotted path>": {"value": ..., "quote": "...", '
        '"locator": "<anchor>", "page": 1, "confidence": 0.0}}}. '
        "quote must be words copied from one passage. "
        "confidence is your own number from 0 to 1. "
        "Omit a path you cannot support. "
        "Required paths: "
        + ", ".join(required_paths(schema) or ["(none)"])
        + ".\n"
        + orjson.dumps(schema).decode()
    )


def required_paths(schema: dict[str, object], prefix: str = "") -> list[str]:
    """Dotted paths named by JSON Schema ``required``, including nested objects."""
    found: list[str] = []
    required = schema.get("required")
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return found
    names = [str(item) for item in required] if isinstance(required, list) else []
    for name in names:
        path = f"{prefix}.{name}" if prefix else name
        child = properties.get(name)
        if isinstance(child, dict) and child.get("type") == "object":
            nested = required_paths(child, path)
            found.extend(nested or [path])
        else:
            found.append(path)
    return found


def interpret(
    raw: str,
    schema: dict[str, object],
    passages: list[dict[str, object]],
    *,
    threshold: float | None = None,
) -> dict[str, object]:
    """Turn one model answer into per-field results. Non-JSON is an error."""
    parsed = _object(raw)
    reports = _reports(parsed, schema)
    minimum = _threshold(threshold)
    fields = [_judge(item, passages, minimum) for item in reports]
    fields = _conflicts(fields)
    return {
        "result": _nest(_present(fields)),
        "fields": fields,
        "exceptions": [str(item["path"]) for item in fields if item.get("status") != "extracted"],
    }


def merge_interpretations(
    parts: list[dict[str, object]], schema: dict[str, object], passages: list[dict[str, object]]
) -> dict[str, object]:
    """Merge chunk results. Two different verified values for one path conflict."""
    by_path: dict[str, list[dict[str, object]]] = {}
    for part in parts:
        rows = part.get("fields")
        if not isinstance(rows, list):
            continue
        for item in rows:
            if isinstance(item, dict):
                by_path.setdefault(str(item.get("path") or ""), []).append(item)
    fields: list[dict[str, object]] = []
    for path in required_paths(schema) or list(by_path):
        chosen = _pick(by_path.get(path, []))
        if chosen is None:
            chosen = _missing(path)
        fields.append(chosen)
    for path, rows in by_path.items():
        if path and path not in {str(item.get("path")) for item in fields}:
            picked = _pick(rows)
            if picked is not None:
                fields.append(picked)
    del passages
    return {
        "result": _nest(_present(fields)),
        "fields": fields,
        "exceptions": [str(item["path"]) for item in fields if item.get("status") != "extracted"],
    }


def _present(fields: list[dict[str, object]]) -> dict[str, object]:
    return {
        str(item["path"]): item["value"]
        for item in fields
        if item.get("value") is not None and str(item.get("path") or "")
    }


def _reports(parsed: dict[str, object], schema: dict[str, object]) -> list[dict[str, object]]:
    raw_fields = parsed.get("fields")
    source = raw_fields if isinstance(raw_fields, dict) else parsed
    reports: list[dict[str, object]] = []
    for path, value in _leaves(source):
        if isinstance(value, dict) and "value" in value:
            reports.append({"path": path, **value})
        else:
            reports.append({"path": path, "value": value})
    have = {str(item["path"]) for item in reports}
    reports.extend({"path": path} for path in required_paths(schema) if path not in have)
    _mark_type_errors(schema, reports)
    return reports


def _mark_type_errors(schema: dict[str, object], reports: list[dict[str, object]]) -> None:
    """A leaf whose JSON type disagrees with the schema is invalid, on that leaf."""
    result = _nest(
        {str(item["path"]): item.get("value") for item in reports if "value" in item}
    )
    bad: set[str] = set()
    for error in Draft202012Validator(schema).iter_errors(result):
        if error.path:
            bad.add(".".join(str(part) for part in error.path))
    for item in reports:
        if str(item.get("path") or "") in bad:
            item["type_error"] = True


def _judge(
    item: dict[str, object], passages: list[dict[str, object]], threshold: float
) -> dict[str, object]:
    path = str(item.get("path") or "")
    if item.get("type_error") is True:
        return _invalid(path, item.get("value"), str(item.get("quote") or ""))
    if "value" not in item or item.get("value") is None:
        return _missing(path)
    quote = str(item.get("quote") or "")
    located = _locate(passages, quote)
    confidence = _confidence(item.get("confidence"))
    verified = located is not None
    if not verified and quote == "" and _value_in_source(item.get("value"), passages):
        verified = True
        located = _locate_value(passages, item.get("value"))
    if not verified:
        status = "missing"
    elif not _supported(item.get("value"), quote or str(item.get("value") or "")):
        status = "invalid"
    elif confidence < threshold:
        status = "low_confidence"
    else:
        status = "extracted"
    page, locator = located if located is not None else (None, "")
    return {
        "path": path,
        "value": item.get("value"),
        "quote": quote or (str(item.get("value")) if verified else ""),
        "page": page,
        "locator": locator,
        "confidence": confidence,
        "quote_verified": verified,
        "status": status,
    }


def _conflicts(fields: list[dict[str, object]]) -> list[dict[str, object]]:
    return fields


def _pick(rows: list[dict[str, object]]) -> dict[str, object] | None:
    verified = [row for row in rows if row.get("quote_verified") and row.get("status") != "missing"]
    if not verified:
        return rows[0] if rows else None
    values = {orjson.dumps(row.get("value"), option=orjson.OPT_SORT_KEYS) for row in verified}
    if len(values) > 1:
        chosen = dict(verified[0])
        chosen["status"] = "conflicting"
        return chosen
    return verified[0]


def _supported(value: object, quote: str) -> bool:
    """The value is in the quote, or its digits are, so a normalised number still counts."""
    if value is None:
        return True
    folded_quote = " ".join(quote.split()).casefold()
    folded = " ".join(str(value).split()).casefold()
    if folded and folded in folded_quote:
        return True
    if isinstance(value, bool):
        return False
    if isinstance(value, int | float):
        digits = "".join(ch for ch in str(value) if ch.isdigit())
        return bool(digits) and digits in "".join(ch for ch in quote if ch.isdigit())
    return False


def _invalid(path: str, value: object, quote: str) -> dict[str, object]:
    row = _missing(path)
    row["value"] = value
    row["quote"] = quote
    row["status"] = "invalid"
    return row


def _missing(path: str) -> dict[str, object]:
    return {
        "path": path,
        "value": None,
        "quote": "",
        "page": None,
        "locator": "",
        "confidence": 0.0,
        "quote_verified": False,
        "status": "missing",
    }


def _locate(passages: list[dict[str, object]], quote: str) -> tuple[object, str] | None:
    if not quote.strip():
        return None
    for item in passages:
        if _contains(str(item.get("text") or ""), quote):
            return item.get("page"), str(item.get("anchor") or "")
    return None


def _locate_value(passages: list[dict[str, object]], value: object) -> tuple[object, str] | None:
    return _locate(passages, str(value))


def _value_in_source(value: object, passages: list[dict[str, object]]) -> bool:
    if isinstance(value, (dict, list)) or value is None or isinstance(value, bool):
        return False
    return _locate(passages, str(value)) is not None


def _confidence(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0.0
    number = float(value)
    if number < 0:
        return 0.0
    if number > 1:
        return 1.0
    return number


def _threshold(value: float | None) -> float:
    if value is not None:
        return value
    raw = getattr(get_settings(), "extraction_min_confidence", 0.8)
    try:
        return float(raw)
    except TypeError, ValueError:
        return 0.8


def _object(raw: str) -> dict[str, object]:
    from ar_common.errors import ArError, ErrorCode  # noqa: PLC0415

    try:
        parsed = orjson.loads(raw)
    except orjson.JSONDecodeError as exc:
        raise ArError(ErrorCode.INVALID_STATE, "The extraction was not JSON.") from exc
    if not isinstance(parsed, dict):
        raise ArError(ErrorCode.INVALID_STATE, "The extraction was not a JSON object.")
    return parsed


def _leaves(value: object, prefix: str = "") -> list[tuple[str, object]]:
    if isinstance(value, dict) and prefix and "value" in value:
        return [(prefix, value)]
    if not isinstance(value, dict):
        return [(prefix, value)] if prefix else []
    found: list[tuple[str, object]] = []
    for key, item in value.items():
        path = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(item, dict) and "value" not in item:
            found.extend(_leaves(item, path))
        else:
            found.append((path, item))
    return found


def _nest(flat: dict[str, object]) -> dict[str, object]:
    root: dict[str, object] = {}
    for path, value in flat.items():
        cursor = root
        parts = path.split(".")
        for part in parts[:-1]:
            nxt = cursor.get(part)
            if not isinstance(nxt, dict):
                nxt = {}
                cursor[part] = nxt
            cursor = nxt
        if parts:
            cursor[parts[-1]] = value
    return root


def _join(passages: list[dict[str, object]]) -> str:
    return "\n\n".join(str(item.get("text") or "") for item in passages)

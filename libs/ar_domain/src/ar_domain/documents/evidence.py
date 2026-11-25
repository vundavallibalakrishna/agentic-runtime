"""Per-field extraction. The model fills values. The code checks the quotes.

A field is extracted only when its quote is in the source and its confidence is
at least the configured threshold. A missing required field is reported, not a
reason to throw away the fields that were found. Long text is split when it
does not fit the model's usable window.
"""

from __future__ import annotations

import hashlib
import re

import orjson
from dateutil import parser as date_parser  # type: ignore[import-untyped]
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
    fields = [_judge(item, passages, minimum, schema) for item in reports]
    fields = _conflicts(fields)
    return {
        "result": _nest(_present(fields)),
        "fields": fields,
        "exceptions": [str(item["path"]) for item in fields if item.get("status") != "extracted"],
    }


def merge_interpretations(
    parts: list[dict[str, object]], schema: dict[str, object], passages: list[dict[str, object]]
) -> dict[str, object]:
    """Merge chunk results. Arrays are concatenated. Other paths conflict when they disagree."""
    by_path: dict[str, list[dict[str, object]]] = {}
    for part in parts:
        rows = part.get("fields")
        if not isinstance(rows, list):
            continue
        for item in rows:
            if isinstance(item, dict):
                by_path.setdefault(str(item.get("path") or ""), []).append(item)
    fields: list[dict[str, object]] = []
    seen: set[str] = set()
    array_bases = {_array_base(path) for path in by_path if _array_base(path)}
    for base in sorted(item for item in array_bases if item):
        fields.extend(_merge_array(base, by_path))
        seen.add(base)
    for path in required_paths(schema) or list(by_path):
        if path in seen or _array_base(path):
            continue
        chosen = _pick(_merged_values(by_path.get(path, [])))
        if chosen is None:
            chosen = _missing(path)
        fields.append(chosen)
        seen.add(path)
    for path, rows in by_path.items():
        if not path or path in seen or _array_base(path):
            continue
        picked = _pick(_merged_values(rows))
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
    result = _nest({str(item["path"]): item.get("value") for item in reports if "value" in item})
    bad: set[str] = set()
    for error in Draft202012Validator(schema).iter_errors(result):
        if error.path:
            bad.add(".".join(str(part) for part in error.path))
    for item in reports:
        if str(item.get("path") or "") in bad:
            item["type_error"] = True


def _judge(
    item: dict[str, object],
    passages: list[dict[str, object]],
    threshold: float,
    schema: dict[str, object],
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
    elif not _supported(
        item.get("value"), quote or str(item.get("value") or ""), _type_of(schema, path)
    ):
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
    """One row per path. Two verified values for that path are a conflict."""
    grouped: dict[str, list[dict[str, object]]] = {}
    order: list[str] = []
    for item in fields:
        path = str(item.get("path") or "")
        if path not in grouped:
            order.append(path)
        grouped.setdefault(path, []).append(item)
    chosen: list[dict[str, object]] = []
    for path in order:
        rows = grouped[path]
        if _array_base(path):
            chosen.extend(rows)
            continue
        picked = _pick(rows)
        if picked is not None:
            chosen.append(picked)
    return chosen


def _array_base(path: str) -> str:
    """The name before the first numeric index, or empty when the path is not an item."""
    parts = path.split(".")
    for index, part in enumerate(parts):
        if part.isdigit():
            return ".".join(parts[:index])
    return ""


def _merge_array(base: str, by_path: dict[str, list[dict[str, object]]]) -> list[dict[str, object]]:
    """Concatenate item evidence from every chunk and drop a repeated value."""
    depth = len([part for part in base.split(".") if part]) if base else 0
    leaves: list[tuple[str, str, dict[str, object]]] = []
    for path, rows in by_path.items():
        if _array_base(path) != base:
            continue
        parts = path.split(".")
        tail = ".".join(parts[depth + 1 :])
        for row in rows:
            key = orjson.dumps(row.get("value"), option=orjson.OPT_SORT_KEYS).decode()
            leaves.append((tail, f"{tail}|{key}", dict(row)))
    merged: list[dict[str, object]] = []
    seen: set[str] = set()
    next_index: dict[str, int] = {}
    for tail, marker, row in leaves:
        if marker in seen:
            continue
        seen.add(marker)
        slot = next_index.get(tail, 0)
        next_index[tail] = slot + 1
        row["path"] = f"{base}.{slot}" if not tail else f"{base}.{slot}.{tail}"
        if not base:
            row["path"] = str(slot) if not tail else f"{slot}.{tail}"
        merged.append(row)
    return merged


def _merged_values(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """A list value is the concatenation of the chunk lists, with duplicates removed."""
    if not rows or not any(isinstance(row.get("value"), list) for row in rows):
        return rows
    combined: list[object] = []
    seen: set[str] = set()
    evidence: list[dict[str, object]] = []
    for row in rows:
        value = row.get("value")
        items = value if isinstance(value, list) else [value]
        for item in items:
            key = orjson.dumps(item, option=orjson.OPT_SORT_KEYS).decode()
            if key in seen:
                continue
            seen.add(key)
            combined.append(item)
            evidence.append(
                {
                    "value": item,
                    "quote": row.get("quote"),
                    "page": row.get("page"),
                    "locator": row.get("locator"),
                    "confidence": row.get("confidence"),
                    "status": row.get("status"),
                }
            )
    head = dict(rows[0])
    head["value"] = combined
    head["items"] = evidence
    return [head]


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


def _supported(value: object, quote: str, kind: str = "") -> bool:
    """The quote supports the value, including a normalised number, date or boolean."""
    if value is None:
        return True
    if _contains_text(value, quote):
        return True
    if kind == "boolean" or isinstance(value, bool):
        return _boolean_supported(value, quote)
    if kind in {"number", "integer"} or (
        isinstance(value, int | float) and not isinstance(value, bool)
    ):
        return _number_supported(value, quote)
    return _dates_match(value, quote)


def _contains_text(value: object, quote: str) -> bool:
    folded_quote = " ".join(quote.split()).casefold()
    folded = " ".join(str(value).split()).casefold()
    return bool(folded) and folded in folded_quote


def _number_supported(value: object, quote: str) -> bool:
    wanted = _parse_number(value)
    if wanted is None:
        return False
    for token in re.findall(r"[-+]?(?:[$€£]\s*)?\d[\d,\s]*(?:\.\d+)?", quote):
        found = _parse_number(token)
        if found is not None and found == wanted:
            return True
    return False


def _parse_number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    text = str(value).strip().replace(",", "").replace(" ", "")
    for mark in ("$", "€", "£"):
        text = text.replace(mark, "")
    try:
        return float(text)
    except ValueError:
        return None


def _dates_match(value: object, quote: str) -> bool:
    if not _looks_like_date(str(value)) or not _looks_like_date(quote):
        return False
    wanted = _parse_date(value)
    found = _parse_date(quote)
    return wanted is not None and found is not None and wanted == found


def _looks_like_date(text: str) -> bool:
    stripped = text.strip()
    if re.fullmatch(r"\d{4}-\d{1,2}-\d{1,2}", stripped):
        return True
    return bool(re.search(r"\d", text) and re.search(r"[A-Za-z]", text))


def _parse_date(value: object) -> object:
    text = str(value).strip()
    if not text:
        return None
    try:
        return date_parser.parse(text, fuzzy=True).date()
    except ValueError, OverflowError:
        return None


def _boolean_supported(value: object, quote: str) -> bool:
    wanted = value if isinstance(value, bool) else _boolean_value(value)
    if wanted is None:
        return False
    words = set(re.findall(r"[A-Za-z0-9]+", quote.casefold()))
    yes, no = _boolean_synonyms()
    if wanted is True:
        return bool(words & yes) and not bool(words & no)
    return bool(words & no) and not bool(words & yes)


def _boolean_value(value: object) -> bool | None:
    text = str(value).strip().casefold()
    yes, no = _boolean_synonyms()
    if text in yes:
        return True
    if text in no:
        return False
    return None


def _boolean_synonyms() -> tuple[set[str], set[str]]:
    raw = str(getattr(get_settings(), "extraction_boolean_synonyms", "") or "")
    true_text, _, false_text = raw.partition(";")
    yes = {item.strip().casefold() for item in true_text.split(",") if item.strip()}
    no = {item.strip().casefold() for item in false_text.split(",") if item.strip()}
    if not yes:
        yes = {"yes", "true", "y"}
    if not no:
        no = {"no", "false", "n"}
    return yes, no


def _type_of(schema: dict[str, object], path: str) -> str:
    node: object = schema
    for part in path.split("."):
        if not isinstance(node, dict):
            return ""
        node = node.get("items") if part.isdigit() else _property(node, part)
    if not isinstance(node, dict):
        return ""
    kind = node.get("type")
    return kind if isinstance(kind, str) else ""


def _property(node: dict[str, object], name: str) -> object:
    properties = node.get("properties")
    if not isinstance(properties, dict):
        return None
    return properties.get(name)


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


_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)


def _object(raw: str) -> dict[str, object]:
    from ar_common.errors import ArError, ErrorCode  # noqa: PLC0415

    try:
        parsed = _decode_json(raw)
    except orjson.JSONDecodeError as exc:
        raise ArError(ErrorCode.INVALID_STATE, "The extraction was not JSON.") from exc
    if not isinstance(parsed, dict):
        raise ArError(ErrorCode.INVALID_STATE, "The extraction was not a JSON object.")
    return parsed


def _decode_json(raw: str) -> object:
    """Strict JSON, or the same object inside a fence or a short prefix."""
    text = raw.strip()
    fenced = _FENCE.search(text)
    if fenced:
        text = fenced.group(1).strip()
    try:
        return orjson.loads(text)
    except orjson.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return orjson.loads(text[start : end + 1])
        raise


def response_schema(schema: dict[str, object]) -> dict[str, object]:
    """The object the model is asked to return: one evidence record per field."""
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["fields"],
        "properties": {"fields": {"type": "object"}, "source": schema},
    }


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

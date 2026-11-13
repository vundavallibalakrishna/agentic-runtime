"""Answers that cite a real passage, or say the passage was not found.

A model may phrase the answer. It may not invent an anchor or a quote. When
the retrieved passages do not support a claim, the result says so.
"""

from __future__ import annotations

import re
from collections.abc import Callable

import orjson

from ar_common.wrapping import wrap_untrusted
from ar_domain.documents.chunk import RETRIEVAL_BUDGET, retrieve, score
from ar_domain.pii.analyzer import Masking, redact

Ask = Callable[[str, str], str | None]
_QUOTE = 240
_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_PHONE = re.compile(r"(?:\+?\d[\d\-\s().]{7,}\d)")
_MISSING = "The document does not contain a passage that supports this."


def summarise(
    document: dict[str, object], ask: Ask | None, *, aggressive: bool = False
) -> dict[str, object]:
    passages = _prepare_passages(_passages(document), aggressive=aggressive)
    chosen = retrieve(passages, _outline_query(passages))[:8] or passages[:8]
    claims = _model_claims(ask, "Summarise only these passages. One claim per point.", chosen)
    if not claims:
        claims = [_extractive(row) for row in chosen if str(row.get("text") or "").strip()]
    if not claims:
        return _empty_summary(document)
    return {
        "kind": "summary",
        "document_id": str(document.get("id") or ""),
        "title": str(document.get("title") or ""),
        "claims": claims,
        "model_used": any(bool(row.get("model")) for row in claims),
    }


def compare(
    left: dict[str, object],
    right: dict[str, object],
    ask: Ask | None,
    *,
    aggressive: bool = False,
) -> dict[str, object]:
    left = _document_view(left, aggressive=aggressive)
    right = _document_view(right, aggressive=aggressive)
    changes = _diff(left, right)
    notes = _model_notes(ask, changes)
    return {
        "kind": "compare",
        "left_id": str(left.get("id") or ""),
        "right_id": str(right.get("id") or ""),
        "left_title": str(left.get("title") or ""),
        "right_title": str(right.get("title") or ""),
        "shared_sections": len(
            {str(row.get("heading") or "") for row in _passages(left)}
            & {str(row.get("heading") or "") for row in _passages(right)}
        ),
        "changes": changes,
        "notes": notes,
        "model_used": bool(notes),
    }


def check(
    document: dict[str, object],
    requirements: list[str],
    ask: Ask | None,
    *,
    label: str = "",
    aggressive: bool = False,
    model_id: str = "",
    rule_set_id: str = "",
    rule_set_version: str = "",
) -> dict[str, object]:
    """Judge statements. A quote is accepted only when it is in the stored passage."""
    from ar_domain.documents.judgement import judge_items  # noqa: PLC0415

    items = [
        (f"s{index}", item.strip())
        for index, item in enumerate(requirements, start=1)
        if item.strip()
    ]
    rows = judge_items(
        document,
        items,
        ask,
        model_id=model_id,
        rule_set_id=rule_set_id,
        rule_set_version=rule_set_version,
        aggressive=aggressive,
    )
    return {
        "kind": "check",
        "document_id": str(document.get("id") or ""),
        "label": label,
        "rows": rows,
        "model_used": any(bool(row.get("model")) for row in rows),
    }


def gaps(
    document: dict[str, object],
    requirements: list[str],
    ask: Ask | None,
    *,
    aggressive: bool = False,
) -> dict[str, object]:
    report = check(document, requirements, ask, label="gaps", aggressive=aggressive)
    raw = report["rows"]
    rows = raw if isinstance(raw, list) else []
    found = [row for row in rows if isinstance(row, dict) and row.get("verdict") != "supported"]
    if not found:
        found.append(
            {
                "requirement": "",
                "statement": "",
                "verdict": "not_judged",
                "reason": "No gap was found for the supplied statements.",
                "citation": None,
                "model": False,
                "model_id": "",
                "prompt_hash": "",
                "passage_id": "",
                "quote": "",
            }
        )
    return {
        "kind": "gaps",
        "document_id": str(document.get("id") or ""),
        "rows": found,
        "model_used": report["model_used"],
    }


def rewrite_text(
    original: str, instruction: str, ask: Ask | None, *, aggressive: bool = False
) -> str:
    """Return proposed text. The caller stores it as a review, not as the document."""
    shown = prepare_analysis_text(original, aggressive=aggressive)
    proposed = ""
    if ask is not None and shown.strip():
        evidence = wrap_untrusted(source="document", content=shown)
        raw = ask(
            "Rephrase the passage. Do not add facts that are not in it. "
            'Return JSON {"text": "..."}.',
            f"Instruction: {instruction}\n\n{evidence}",
        )
        parsed = _object(raw)
        if parsed is not None:
            proposed = str(parsed.get("text") or "").strip()
    if not proposed or proposed == shown:
        proposed = _local_rewrite(shown, instruction)
    return proposed


def extract_fields(
    document: dict[str, object],
    fields: list[str],
    ask: Ask | None,
    *,
    aggressive: bool = False,
) -> dict[str, object]:
    """Read named values out of a document. A value is returned only with the words that state it.

    A field the document does not state comes back empty. Nothing is guessed from a
    passage that merely shares a word with the field name.
    """
    passages = _prepare_passages(_passages(document), aggressive=aggressive)
    values = [_extract_one(document, passages, name, ask) for name in fields]
    return {
        "kind": "extract",
        "document_id": str(document.get("id") or ""),
        "fields": values,
        "model_used": ask is not None,
    }


def _extract_one(
    document: dict[str, object], passages: list[dict[str, object]], name: str, ask: Ask | None
) -> dict[str, object]:
    candidates = _candidates(passages, name)
    found = _asked_value(candidates, name, ask) or _labelled_value(candidates, name)
    if found is None:
        return {"field": name, "value": None, "reason": _MISSING, "citation": None, "confidence": 0}
    hit, value, quote, confidence = found
    return {
        "field": name,
        "value": value,
        "reason": "",
        "citation": {
            "document_id": str(document.get("id") or ""),
            "anchor": str(hit.get("anchor") or ""),
            "page": int(str(hit.get("page") or 0)),
            "quote": quote[:_QUOTE],
        },
        "confidence": confidence,
    }


_Found = tuple[dict[str, object], str, str, float]


def _candidates(passages: list[dict[str, object]], name: str) -> list[dict[str, object]]:
    """Passages to read for a field: those sharing its words first, then the rest, to the budget.

    A field name rarely uses the document's own wording, so a passage is not ruled
    out for sharing no word with it while there is room to show it.
    """
    ranked = sorted(
        enumerate(passages),
        key=lambda item: (-score(name, str(item[1].get("text") or "")), item[0]),
    )
    chosen: list[dict[str, object]] = []
    used = 0
    for _index, row in ranked:
        size = len(str(row.get("text") or ""))
        if chosen and used + size > RETRIEVAL_BUDGET:
            continue
        chosen.append(row)
        used += size
    return chosen


def _asked_value(candidates: list[dict[str, object]], name: str, ask: Ask | None) -> _Found | None:
    """The model's reading, kept only when its quote and value are in a passage word for word."""
    if ask is None or not candidates:
        return None
    raw = ask(
        f'Extract the field "{name}" only if a passage states it. '
        'Return JSON {"value": "", "quote": "", "anchor": ""}. The value and the quote are '
        "copied word for word from one passage; the quote is the sentence that states the "
        "value and the anchor is that passage's anchor. Use an empty value when it is absent.",
        _evidence(candidates),
    )
    parsed = _object(raw)
    if parsed is None:
        return None
    value = str(parsed.get("value") or "").strip()
    quote = str(parsed.get("quote") or "").strip()
    if not value or not quote:
        return None
    named = _by_anchor(candidates, str(parsed.get("anchor") or ""))
    for row in [named, *candidates] if named is not None else candidates:
        text = str(row.get("text") or "")
        if _contains(text, quote) and _contains(text, value):
            return row, value, quote, 0.9
    return None


def _labelled_value(candidates: list[dict[str, object]], name: str) -> _Found | None:
    """A value the document labels with the field's own name, as in ``Name: value``."""
    pattern = re.compile(rf"{re.escape(name)}\s*[:\-]\s*(.+)", re.IGNORECASE)
    for row in candidates:
        for line in str(row.get("text") or "").splitlines():
            match = pattern.search(line)
            if match:
                return row, match.group(1).strip()[:200], line.strip(), 0.6
    return None


def prepare_analysis_text(text: str, *, aggressive: bool) -> str:
    """Text a document check may show a model.

    The default keeps dates, locations and control ids. ``aggressive`` is the
    tenant opt-in that runs the outbound recognisers.
    """
    if not text:
        return text
    if aggressive:
        return redact(text, enabled=True, profile="outbound", masking=Masking.thorough())
    return redact(text, enabled=True, profile="verbatim")


def redaction_preview(text: str) -> dict[str, object]:
    """Return redacted text only. The original is not part of the result."""
    masked = _EMAIL.sub("[EMAIL]", text)
    masked = _PHONE.sub("[PHONE]", masked)
    masked = redact(masked, enabled=True, profile="outbound", masking=Masking.thorough())
    counts: dict[str, int] = {}
    for token in re.findall(r"\[([A-Z_]+)\]", masked):
        counts[token] = counts.get(token, 0) + 1
    return {
        "kind": "redact",
        "redacted": masked,
        "entities": [{"type": name, "count": count} for name, count in sorted(counts.items())],
    }


def line_hunks(before: str, after: str) -> list[dict[str, object]]:
    import difflib  # noqa: PLC0415

    left = before.splitlines()
    right = after.splitlines()
    hunks: list[dict[str, object]] = []
    matcher = difflib.SequenceMatcher(a=left, b=right)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        hunks.append(
            {
                "id": f"h{len(hunks) + 1}",
                "op": tag,
                "start": i1,
                "end": i2,
                "before": "\n".join(left[i1:i2]),
                "after": "\n".join(right[j1:j2]),
                "decision": "",
            }
        )
    return hunks


def apply_hunks(original: str, hunks: list[dict[str, object]]) -> str:
    lines = original.splitlines()
    ordered = sorted(hunks, key=lambda row: int(str(row.get("start") or 0)), reverse=True)
    for hunk in ordered:
        if hunk.get("decision") != "accept":
            continue
        start = int(str(hunk.get("start") or 0))
        end = int(str(hunk.get("end") or start))
        replacement = str(hunk.get("after") or "")
        lines[start:end] = replacement.splitlines() if replacement else []
    return "\n".join(lines)


def table_items(filename: str, data: bytes, *, limit: int = 40) -> list[tuple[str, str]]:
    """The rows of a delimited file as items: each row's longest cell, named by its first.

    A list kept as a table has one item a row. Read as prose it has none, and its
    file name was offered as the only item.
    """
    import csv  # noqa: PLC0415
    import io  # noqa: PLC0415

    suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if suffix not in {"csv", "tsv"} or not data:
        return []
    text = data.decode("utf-8-sig", errors="replace")
    rows = list(csv.reader(io.StringIO(text), delimiter="\t" if suffix == "tsv" else ","))
    items: list[tuple[str, str]] = []
    # The first row names the columns.
    for index, row in enumerate(rows[1:], start=1):
        cells = [cell.strip() for cell in row if cell.strip()]
        if not cells:
            continue
        statement = max(cells, key=len)
        first = cells[0]
        items.append((first if first != statement else f"r{index}", statement))
        if len(items) >= limit:
            break
    return items


def requirements_from(document: dict[str, object], *, limit: int = 40) -> list[str]:
    found: list[str] = []
    for passage in _passages(document):
        heading = str(passage.get("heading") or "").strip()
        if heading and heading not in found and not heading.startswith("Page "):
            found.append(heading)
        for line in str(passage.get("text") or "").splitlines():
            stripped = line.strip()
            match = re.match(r"^(?:\d+[.)]|[-*])\s+(\S.*)$", stripped)
            if match:
                item = match.group(1).strip()
                if item and item not in found:
                    found.append(item)
            if len(found) >= limit:
                return found
    return found[:limit]


def _prepare_passages(
    passages: list[dict[str, object]], *, aggressive: bool
) -> list[dict[str, object]]:
    prepared: list[dict[str, object]] = []
    for row in passages:
        copied = dict(row)
        copied["text"] = prepare_analysis_text(str(row.get("text") or ""), aggressive=aggressive)
        prepared.append(copied)
    return prepared


def _document_view(document: dict[str, object], *, aggressive: bool) -> dict[str, object]:
    copied = dict(document)
    copied["passages"] = _prepare_passages(_passages(document), aggressive=aggressive)
    return copied


def _diff(left: dict[str, object], right: dict[str, object]) -> list[dict[str, object]]:
    left_rows = _passages(left)
    right_rows = _passages(right)
    right_by_heading = {str(row.get("heading") or ""): row for row in right_rows}
    used: set[str] = set()
    changes: list[dict[str, object]] = []
    for row in left_rows:
        heading = str(row.get("heading") or "")
        other = right_by_heading.get(heading)
        if other is None:
            changes.append(_change("removed", row, None))
            continue
        used.add(heading)
        if _norm(str(row.get("text") or "")) != _norm(str(other.get("text") or "")):
            changes.append(_change("changed", row, other))
    for row in right_rows:
        heading = str(row.get("heading") or "")
        if heading not in used and heading not in {
            str(item.get("heading") or "") for item in left_rows
        }:
            changes.append(_change("added", None, row))
    return changes


def _change(
    op: str, left: dict[str, object] | None, right: dict[str, object] | None
) -> dict[str, object]:
    return {
        "op": op,
        "left_anchor": "" if left is None else str(left.get("anchor") or ""),
        "right_anchor": "" if right is None else str(right.get("anchor") or ""),
        "left_page": 0 if left is None else int(str(left.get("page") or 0)),
        "right_page": 0 if right is None else int(str(right.get("page") or 0)),
        "heading": str((left or right or {}).get("heading") or ""),
        "before": "" if left is None else str(left.get("text") or "")[:800],
        "after": "" if right is None else str(right.get("text") or "")[:800],
    }


def _model_notes(ask: Ask | None, changes: list[dict[str, object]]) -> list[dict[str, object]]:
    if ask is None or not changes:
        return []
    sample = changes[:8]
    lines = [
        f"{row.get('op')} {row.get('heading')} "
        f"before={str(row.get('before') or '')[:180]} after={str(row.get('after') or '')[:180]}"
        for row in sample
    ]
    raw = ask(
        "Describe these document changes in one sentence each. "
        'Return JSON {"notes": [{"heading": "", "text": ""}]}. '
        "Do not add a change that is not in the list.",
        wrap_untrusted(source="document", content="\n".join(lines)),
    )
    parsed = _object(raw)
    raw_notes = None if parsed is None else parsed.get("notes")
    if not isinstance(raw_notes, list):
        return []
    known = {str(row.get("heading") or "") for row in sample}
    notes: list[dict[str, object]] = []
    for item in raw_notes:
        if not isinstance(item, dict):
            continue
        heading = str(item.get("heading") or "")
        text = str(item.get("text") or "").strip()
        if heading in known and text:
            notes.append({"heading": heading, "text": text[:400]})
    return notes


def _model_claims(
    ask: Ask | None, task: str, passages: list[dict[str, object]]
) -> list[dict[str, object]]:
    if ask is None or not passages:
        return []
    raw = ask(
        task + " Every claim needs an anchor from the passages and a quote that is an exact "
        'substring. Return JSON {"claims": [{"text": "", "anchor": "", "quote": ""}]}. '
        "If nothing is supported, return an empty claims list.",
        _evidence(passages),
    )
    parsed = _object(raw)
    raw_claims = None if parsed is None else parsed.get("claims")
    if not isinstance(raw_claims, list):
        return []
    claims: list[dict[str, object]] = []
    for item in raw_claims:
        if not isinstance(item, dict):
            continue
        passage = _by_anchor(passages, str(item.get("anchor") or ""))
        if passage is None:
            continue
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        quote = str(item.get("quote") or "")
        body = str(passage.get("text") or "")
        if not _contains(body, quote):
            quote = _first_sentence(body)
        claims.append(
            {
                "text": text[:500],
                "anchor": str(passage.get("anchor") or ""),
                "page": int(str(passage.get("page") or 0)),
                "quote": quote[:_QUOTE],
                "model": True,
            }
        )
    return claims


def _extractive(row: dict[str, object]) -> dict[str, object]:
    sentence = _first_sentence(str(row.get("text") or ""))
    heading = str(row.get("heading") or "")
    text = sentence if sentence else heading
    return {
        "text": text[:500],
        "anchor": str(row.get("anchor") or ""),
        "page": int(str(row.get("page") or 0)),
        "quote": sentence[:_QUOTE],
        "model": False,
    }


def _empty_summary(document: dict[str, object]) -> dict[str, object]:
    return {
        "kind": "summary",
        "document_id": str(document.get("id") or ""),
        "title": str(document.get("title") or ""),
        "claims": [],
        "note": _MISSING,
        "model_used": False,
    }


def _evidence(passages: list[dict[str, object]]) -> str:
    blocks = []
    for row in passages:
        body = (
            f"anchor: {row.get('anchor')} page: {row.get('page')} "
            f"heading: {row.get('heading')}\n{row.get('text')}"
        )
        blocks.append(wrap_untrusted(source="document", content=body))
    return "\n".join(blocks)


def _passages(document: dict[str, object]) -> list[dict[str, object]]:
    raw = document.get("passages")
    if not isinstance(raw, list):
        return []
    return [row for row in raw if isinstance(row, dict)]


def _by_anchor(passages: list[dict[str, object]], anchor: str) -> dict[str, object] | None:
    for row in passages:
        if str(row.get("anchor") or "") == anchor:
            return row
    return None


def _object(raw: str | None) -> dict[str, object] | None:
    if not raw:
        return None
    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        value = orjson.loads(raw[start : end + 1])
    except orjson.JSONDecodeError:
        return None
    if not isinstance(value, dict):
        return None
    return {str(key): item for key, item in value.items()}


def _contains(text: str, quote: str) -> bool:
    if not quote.strip():
        return False
    folded = re.sub(r"\s+", " ", text).lower()
    wanted = re.sub(r"\s+", " ", quote).strip().lower()
    return wanted in folded


def _first_sentence(text: str) -> str:
    sentences = _sentences(text)
    if sentences:
        return sentences[0][:_QUOTE]
    return re.sub(r"\s+", " ", text).strip()[:_QUOTE]


def _sentences(text: str) -> list[str]:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return []
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", cleaned) if part.strip()]


def _local_rewrite(original: str, instruction: str) -> str:
    match = re.search(
        r"""replace ['"](.+?)['"] with ['"](.+?)['"]""",
        instruction,
        re.IGNORECASE,
    )
    if match and match.group(1) in original:
        return original.replace(match.group(1), match.group(2), 1)
    parts = [part.strip() for part in re.split(r"(?<=[.!?])\s+", original) if part.strip()]
    if len(parts) > 1:
        return " ".join([*parts[1:], parts[0]])
    return f"{original.rstrip('.')}."


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _outline_query(passages: list[dict[str, object]]) -> str:
    headings = " ".join(str(row.get("heading") or "") for row in passages[:12])
    return headings or "summary"

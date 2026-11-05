"""Redact PII. Presidio is used when the extra is installed."""

import re
from typing import Protocol, cast

from ar_domain.pii.recognizers_in import find_indian

# Dates, places and licence-shaped tokens are evidence in a policy or a DPA.
# Presidio labels "90 days" as DATE_TIME, "Ireland" as LOCATION and "P6" inside
# a control id as US_DRIVER_LICENSE. Analysis keeps those spans.
_EVIDENCE = frozenset(
    {
        "date_time",
        "location",
        "nrp",
        "person",
        "url",
        "us_driver_license",
    }
)


class _Span(Protocol):
    entity_type: str
    start: int
    end: int


class _Engine(Protocol):
    def analyze(self, text: str, language: str) -> list[_Span]: ...


_engine_cache: list[object] = []

# A sandbox path is not a licence. Presidio's US driver-licence pattern matches
# hex groups inside a UUID (``01a1ab39-[US_DRIVER_LICENSE]-…``), and the model
# then cannot reuse the path. The whole path, and any UUID in it, stays.
_UUID = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
_WORKSPACE_PATH = re.compile(
    r"(?:[A-Za-z]:)?(?:/[\w.+\-]+)*?/ar-sandboxes(?:/[\w.+\-]+)+|/workspace(?:/[\w.+\-]+)*"
)


def redact(
    text: str,
    *,
    enabled: bool = True,
    profile: str = "outbound",
    skip_entities: tuple[str, ...] = (),
) -> str:
    """Replace recognised PII with tokens.

    ``outbound`` masks every recogniser. ``analysis`` leaves dates, locations,
    names and control-id shaped tokens in place so a compliance check can read
    them.     ``skip_entities`` names further entity types (case-insensitive) the
    tenant chose not to mask. Run-workspace paths and UUID segments inside
    them are left as written (OQ-66). Disabled callers receive the original text.
    """
    if not enabled or not text:
        return text
    skipped = {name.lower() for name in skip_entities}
    if profile == "analysis":
        skipped |= _EVIDENCE
    protected = _protected_ranges(text)
    spans = [
        span
        for span in (*find_indian(text), *_presidio(text))
        if _closed_span(text, span)
        and str(span["entity"]).lower() not in skipped
        and not _overlaps_protected(span, protected)
    ]
    spans.sort(key=lambda item: int(str(item["start"])), reverse=True)
    updated = text
    for span in spans:
        start = int(str(span["start"]))
        end = int(str(span["end"]))
        kind = str(span["entity"]).upper()
        updated = updated[:start] + f"[{kind}]" + updated[end:]
    return updated


def _protected_ranges(text: str) -> list[tuple[int, int]]:
    """Character ranges that redaction must leave alone."""
    ranges = [(match.start(), match.end()) for match in _UUID.finditer(text)]
    ranges.extend((match.start(), match.end()) for match in _WORKSPACE_PATH.finditer(text))
    return ranges


def _overlaps_protected(span: dict[str, object], ranges: list[tuple[int, int]]) -> bool:
    start = int(str(span["start"]))
    end = int(str(span["end"]))
    return any(start < stop and end > begin for begin, stop in ranges)


def _closed_span(text: str, span: dict[str, object]) -> bool:
    """Keep a hit that ends on a token boundary.

    Presidio's URL pattern treats ``pn`` as a TLD, so ``revenue-by-month.png``
    is reported as ``revenue-by-month.pn`` and the final letter is left behind.
    """
    if str(span.get("entity")) != "url":
        return True
    end = int(str(span["end"]))
    return end >= len(text) or not text[end].isalnum()


def _presidio(text: str) -> list[dict[str, object]]:
    cached = _cached_engine()
    if cached is None:
        return []
    engine = cast("_Engine", cached)
    return [
        {"entity": result.entity_type.lower(), "start": result.start, "end": result.end}
        for result in engine.analyze(text=text, language="en")
    ]


def _cached_engine() -> object | None:
    """Build the Presidio engine once. A missing extra leaves analysis unmasked."""
    if _engine_cache:
        return _engine_cache[0]
    try:
        from presidio_analyzer import AnalyzerEngine  # noqa: PLC0415
    except ImportError:
        return None
    engine = AnalyzerEngine()
    _engine_cache.append(engine)
    return engine

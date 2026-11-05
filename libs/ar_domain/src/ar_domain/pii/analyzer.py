"""Redact PII. Presidio is used when the extra is installed."""

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


def redact(text: str, *, enabled: bool = True, profile: str = "outbound") -> str:
    """Replace recognised PII with tokens.

    ``outbound`` masks every recogniser. ``analysis`` leaves dates, locations,
    names and control-id shaped tokens in place so a compliance check can read
    them. Disabled callers receive the original text.
    """
    if not enabled or not text:
        return text
    spans = [span for span in (*find_indian(text), *_presidio(text)) if _closed_span(text, span)]
    if profile == "analysis":
        spans = [span for span in spans if str(span["entity"]).lower() not in _EVIDENCE]
    spans.sort(key=lambda item: int(str(item["start"])), reverse=True)
    updated = text
    for span in spans:
        start = int(str(span["start"]))
        end = int(str(span["end"]))
        kind = str(span["entity"]).upper()
        updated = updated[:start] + f"[{kind}]" + updated[end:]
    return updated


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

"""Redact PII. Presidio is used when the extra is installed."""

from ar_domain.pii.recognizers_in import find_indian


def redact(text: str, *, enabled: bool = True) -> str:
    """Replace recognised PII with tokens. Disabled tenants receive the original text."""
    if not enabled or not text:
        return text
    spans = [span for span in (*find_indian(text), *_presidio(text)) if _closed_span(text, span)]
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
    try:
        from presidio_analyzer import AnalyzerEngine  # noqa: PLC0415
    except ImportError:
        return []
    engine = AnalyzerEngine()
    return [
        {"entity": result.entity_type.lower(), "start": result.start, "end": result.end}
        for result in engine.analyze(text=text, language="en")
    ]

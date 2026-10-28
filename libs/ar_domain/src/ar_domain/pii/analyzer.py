"""Redact PII. Presidio is used when the extra is installed."""

from ar_domain.pii.recognizers_in import find_indian


def redact(text: str, *, enabled: bool = True) -> str:
    """Replace recognised PII with tokens. Disabled tenants receive the original text."""
    if not enabled or not text:
        return text
    spans = find_indian(text)
    spans.extend(_presidio(text))
    spans.sort(key=lambda item: int(str(item["start"])), reverse=True)
    updated = text
    for span in spans:
        start = int(str(span["start"]))
        end = int(str(span["end"]))
        kind = str(span["entity"]).upper()
        updated = updated[:start] + f"[{kind}]" + updated[end:]
    return updated


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

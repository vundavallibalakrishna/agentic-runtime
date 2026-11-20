"""What a read of a file was like. Stored on the library row, not a new parser."""

from __future__ import annotations

from ar_common.settings import get_settings


def _passage_text(item: object) -> str:
    if isinstance(item, dict):
        return str(item.get("text") or "")
    return str(getattr(item, "text", "") or "")


def quality_record(
    *,
    page_count: int,
    passages: list[object],
    tables: list[object],
    pages_ocr: int,
    engine: str,
) -> dict[str, object]:
    """``ocr``, ``pagesOcr``, ``meanCharsPerPage``, ``tableCount`` and ``warnings``."""
    texts = [_passage_text(item) for item in passages]
    characters = sum(len(text) for text in texts)
    pages = page_count if page_count > 0 else 1
    mean = characters / pages
    name = engine if engine in {"tesseract", "vision"} else "none"
    warnings: list[str] = []
    if name != "none" and mean < float(get_settings().document_low_text_chars):
        warnings.append("low_text")
    if any("\ufffd" in text for text in texts):
        warnings.append("mixed_encoding")
    return {
        "ocr": name,
        "pagesOcr": pages_ocr,
        "meanCharsPerPage": round(mean, 1),
        "tableCount": len(tables),
        "warnings": warnings,
    }


def engine_name(ocr: object) -> str:
    """``vision`` when the reader is the vision alias, otherwise ``tesseract``."""
    name = str(getattr(ocr, "__name__", "") or type(ocr).__name__)
    if "vision" in name.lower():
        return "vision"
    return "tesseract"

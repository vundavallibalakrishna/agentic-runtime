"""Local OCR status. Cloud OCR providers stay unwired.

Tesseract runs in the API process when the binary is on PATH (OQ-61, OQ-73).
Google Document AI, Amazon Textract and Azure Document Intelligence are named
so a caller gets a clear not_live result instead of a silent empty read.
"""

from __future__ import annotations

import shutil

_INSTALL = (
    "Install the tesseract-ocr and tesseract-ocr-eng packages on the API and "
    "ingest images, then restart those processes. Local OCR needs no paid key."
)

CLOUD_ENGINES: dict[str, str] = {
    "google_document_ai": (
        "Google Document AI is not_live. This runtime does not call it. " + _INSTALL
    ),
    "aws_textract": ("Amazon Textract is not_live. This runtime does not call it. " + _INSTALL),
    "azure_document_intelligence": (
        "Azure Document Intelligence is not_live. This runtime does not call it. " + _INSTALL
    ),
}


def normalise_engine(engine: str) -> str:
    """Fold a caller engine name onto the catalogue key."""
    return engine.strip().lower().replace("-", "_").replace(" ", "_")


def tesseract_installed() -> bool:
    """Whether the local OCR binary is on PATH."""
    return shutil.which("tesseract") is not None


def engine_catalogue() -> dict[str, dict[str, str]]:
    """Built versus live labels for the OCR engines a caller can name."""
    live = tesseract_installed()
    rows = {
        "tesseract": {
            "status": "live" if live else "not_live",
            "operator": _INSTALL if not live else "tesseract is on PATH. No provider key is used.",
        }
    }
    for name, message in CLOUD_ENGINES.items():
        rows[name] = {"status": "not_live", "operator": message}
    return rows


def cloud_refusal(engine: str) -> str | None:
    """A not_live message for a cloud engine. None when the caller asked for tesseract."""
    key = normalise_engine(engine)
    if key in {"", "tesseract", "local"}:
        return None
    message = CLOUD_ENGINES.get(key)
    if message is None:
        known = ", ".join(["tesseract", *CLOUD_ENGINES])
        return f"Unknown OCR engine. Use one of: {known}."
    return message

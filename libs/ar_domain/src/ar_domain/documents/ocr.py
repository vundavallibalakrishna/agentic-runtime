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
    """Proof labels for the OCR providers a caller can name.

    Tesseract is ``unit``: it is a local binary, not a model. The vision alias is
    ``unit`` until a configured vision model answers; that result is ``live`` and
    names the model id and the date. Cloud engines stay unwired.
    """
    installed = tesseract_installed()
    rows = {
        "tesseract": {
            "status": "unit" if installed else "text_not_extracted",
            "proof": "unit",
            "operator": (
                "tesseract is on PATH. No provider key is used. Proof: unit."
                if installed
                else _INSTALL + " Without it, an image is text_not_extracted."
            ),
        },
        "vision": {
            "status": "unit",
            "proof": "unit",
            "operator": (
                "The vision alias reads an image when a vision model is set. "
                "A result is live only when that model answers, and the result "
                "names the model id and the date. Otherwise the result is text_not_extracted."
            ),
        },
    }
    for name, message in CLOUD_ENGINES.items():
        rows[name] = {"status": "not_live", "proof": "unit", "operator": message}
    return rows


class VisionReader:
    """OCR through the tenant's vision alias. Proof stays ``unit`` until the model answers."""

    def __init__(self, store: object, tenant_id: object, alias: str = "vision") -> None:
        self.store = store
        self.tenant_id = tenant_id
        self.alias = alias.strip() or "vision"
        self.proof = "unit"
        self.model_id = ""
        self.observed_on = ""

    def __call__(self, data: bytes) -> str:
        from ar_common.time import utcnow  # noqa: PLC0415
        from ar_domain.documents.extract import ExtractError  # noqa: PLC0415
        from ar_domain.documents.model import model_id_for  # noqa: PLC0415
        from ar_domain.documents.vision import VisionError, ask_image  # noqa: PLC0415

        try:
            text = ask_image(
                self.store,
                self.tenant_id,
                alias=self.alias,
                question="Transcribe every visible word. Return only that text.",
                data=data,
                media_type="",
            )
        except VisionError as exc:
            raise ExtractError("text_not_extracted", exc.message) from exc
        self.proof = "live"
        self.model_id = model_id_for(self.store, self.tenant_id, self.alias)  # type: ignore[arg-type]
        self.observed_on = utcnow().date().isoformat()
        return text


def cloud_refusal(engine: str) -> str | None:
    """A not_live message for a cloud engine. None when the caller asked for tesseract."""
    key = normalise_engine(engine)
    if key in {"", "tesseract", "local", "vision"}:
        return None
    message = CLOUD_ENGINES.get(key)
    if message is None:
        known = ", ".join(["tesseract", *CLOUD_ENGINES])
        return f"Unknown OCR engine. Use one of: {known}."
    return message

"""Live proof for M33b. Reads AR_CERT_LLM_API_KEY and does not print it.

OCR uses the local tesseract binary when it is installed. Vision calls the
configured vision model on DeepInfra. A missing binary or a missing vision
model is printed as not_live. The provider key is never written.
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

from ar_domain.documents.ocr import engine_catalogue, tesseract_installed
from ar_domain.documents.vision import VisionError, ask_image
from ar_domain.tools.documents import dispatch_documents

_ROOT = Path(__file__).resolve().parents[1]
_FIXTURES = _ROOT / "docs" / "testing" / "fixtures" / "m33b"
_MODEL = os.environ.get("AR_VISION_MODEL", "Qwen/Qwen2.5-VL-32B-Instruct")
_URL = "https://api.deepinfra.com/v1/openai/chat/completions"


class _OcrStore:
    def __init__(self) -> None:
        self.scanner = "none"
        self.audit_log: list[dict[str, object]] = []
        self.blobs: dict[uuid.UUID, bytes] = {}
        self.files: dict[uuid.UUID, dict[str, object]] = {}


class _VisionStore:
    def __init__(self, key: str) -> None:
        self._key = key

    def _completion_call(
        self, tenant_id: uuid.UUID, alias: str = "vision"
    ) -> tuple[str, dict[str, str], float, bool]:
        del tenant_id, alias
        return _MODEL, {}, 90.0, True

    def _completion_url_for(self, tenant_id: uuid.UUID, alias: str, headers: dict[str, str]) -> str:
        del tenant_id, alias
        headers["Authorization"] = f"Bearer {self._key}"
        return _URL


def _expected() -> list[str]:
    return [
        line.strip()
        for line in (_FIXTURES / "ocr-canary.expected.txt").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _matches(text: str) -> bool:
    folded = " ".join(text.upper().split())
    return all(token.upper() in folded for token in _expected())


def _ocr(lines: list[str]) -> int:
    report = engine_catalogue()
    for name, row in report.items():
        lines.append(f"engine {name} {row['status']}")
    if not tesseract_installed():
        lines.append("OCR not_live tesseract is not installed")
        return 0
    store = _OcrStore()
    tenant = uuid.uuid4()
    user = uuid.uuid4()
    failures = 0
    for name, media in (
        ("ocr-canary.png", "image/png"),
        ("ocr-canary.pdf", "application/pdf"),
    ):
        file_id = uuid.uuid4()
        store.blobs[file_id] = (_FIXTURES / name).read_bytes()
        store.files[file_id] = {"tenant_id": tenant, "name": name, "mime_type": media}
        result = dispatch_documents(
            store,
            "ocr",
            {
                "_tenant_id": tenant,
                "_user_id": user,
                "fileId": str(file_id),
            },
        )
        text = str(result.get("text") or "")
        ok = result.get("is_error") is False and _matches(text)
        lines.append(f"ocr {name} {'PASS' if ok else 'FAIL'}")
        if not ok:
            lines.append(text[:400].replace("\n", " "))
            failures += 1
    refused = dispatch_documents(
        store,
        "ocr",
        {"_tenant_id": tenant, "_user_id": user, "engine": "google_document_ai"},
    )
    cloud_ok = refused.get("code") == "not_live"
    lines.append(f"ocr google_document_ai {'not_live' if cloud_ok else 'FAIL'}")
    if not cloud_ok:
        failures += 1
    return failures


def _vision(lines: list[str], key: str) -> int:
    if not key:
        lines.append("vision not_live AR_CERT_LLM_API_KEY is unset")
        return 0
    if "-vl" not in _MODEL.lower() and "vision" not in _MODEL.lower():
        lines.append(f"vision not_live {_MODEL} is not a vision model name")
        return 0
    png = (_FIXTURES / "ocr-canary.png").read_bytes()
    try:
        answer = ask_image(
            _VisionStore(key),
            uuid.uuid4(),
            alias="vision",
            question="What code is printed in the image? Reply with the code only.",
            data=png,
            media_type="image/png",
        )
    except VisionError as exc:
        lines.append(f"vision not_live {exc.code}")
        return 0
    if key in answer:
        lines.append("vision FAIL key appeared in the answer")
        return 1
    ok = "4821" in answer
    lines.append(f"vision {_MODEL} {'PASS' if ok else 'FAIL'}")
    lines.append(answer[:300].replace("\n", " "))
    return 0 if ok else 1


def main() -> int:
    key = os.environ.get("AR_CERT_LLM_API_KEY", "").strip()
    lines: list[str] = []
    failures = _ocr(lines)
    failures += _vision(lines, key)
    if key and key in "\n".join(lines):
        lines.append("FAIL key appeared in the proof output")
        failures += 1
    sys.stdout.write("\n".join(lines) + "\n")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

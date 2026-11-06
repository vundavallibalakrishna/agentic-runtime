"""OCR canary and image.ask. Cloud OCR stays not_live. Vision fails closed."""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx
import pytest

from ar_domain.demo_ids import demo_id
from ar_domain.documents.ocr import engine_catalogue, tesseract_installed
from ar_domain.tools.documents import dispatch_documents
from ar_domain.tools.handlers import dispatch
from ar_domain.tools.pipeline import ToolPipeline
from ar_domain.tools.seed_tools import ensure_m33b
from ar_testing.demo import demo_store

if TYPE_CHECKING:
    from ar_domain.chat.service import ChatService

_FIXTURES = Path(__file__).resolve().parents[4] / "docs" / "testing" / "fixtures" / "m33b"
_KEY = "sealed-vision-key"


def _expected() -> list[str]:
    return [
        line.strip()
        for line in (_FIXTURES / "ocr-canary.expected.txt").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _matches(text: str, expected: list[str]) -> bool:
    folded = " ".join(text.upper().split())
    return all(token.upper() in folded for token in expected)


def _attach(store: Any, tenant: uuid.UUID, data: bytes, name: str, media: str) -> uuid.UUID:
    file_id = uuid.uuid4()
    store.blobs[file_id] = data
    store.files[file_id] = {"tenant_id": tenant, "name": name, "mime_type": media}
    return file_id


def _args(tenant: uuid.UUID, user: uuid.UUID, **extra: object) -> dict[str, object]:
    body: dict[str, object] = {"_tenant_id": tenant, "_user_id": user}
    body.update(extra)
    return body


def test_canary_fixture_lists_the_golden_strings() -> None:
    expected = _expected()
    assert expected == ["M33B CANARY", "CODE 4821"]
    assert (_FIXTURES / "ocr-canary.png").stat().st_size > 1000
    assert (_FIXTURES / "ocr-canary.pdf").stat().st_size > 1000


def test_engine_catalogue_marks_cloud_ocr_not_live() -> None:
    report = engine_catalogue()
    assert report["tesseract"]["status"] == ("live" if tesseract_installed() else "not_live")
    assert (
        "tesseract-ocr" in report["tesseract"]["operator"]
        or report["tesseract"]["status"] == "live"
    )
    for name in ("google_document_ai", "aws_textract", "azure_document_intelligence"):
        assert report[name]["status"] == "not_live"
        assert "not_live" in report[name]["operator"]
        assert "tesseract-ocr" in report[name]["operator"]


def test_ocr_tool_stores_the_canary_and_hides_it_from_another_tenant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = _expected()

    def fake_ocr(_data: bytes) -> str:
        return "\n".join(expected)

    monkeypatch.setattr("ar_domain.documents.extract._tesseract", fake_ocr)
    store = demo_store()
    tenant = demo_id("tenant")
    user = demo_id("admin")
    file_id = _attach(
        store, tenant, (_FIXTURES / "ocr-canary.png").read_bytes(), "ocr-canary.png", "image/png"
    )
    saved = dispatch_documents(store, "ocr", _args(tenant, user, fileId=str(file_id)))
    assert saved["is_error"] is False
    assert _matches(str(saved["text"]), expected)
    document_id = str(saved["structured"]["presentation"]["documentId"])  # type: ignore[index]
    again = dispatch_documents(store, "ocr", _args(tenant, user, documentId=document_id))
    assert _matches(str(again["text"]), expected)
    other = dispatch_documents(
        store, "ocr", _args(uuid.uuid4(), uuid.uuid4(), documentId=document_id)
    )
    assert other["is_error"] is True
    assert other["code"] == "not_found"


def test_scanned_pdf_canary_goes_through_ocr(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[bytes] = []

    def fake_ocr(data: bytes) -> str:
        seen.append(data[:3])
        return "\n".join(_expected())

    monkeypatch.setattr("ar_domain.documents.extract._tesseract", fake_ocr)

    def no_pillow(_page: object) -> list[bytes]:
        raise AssertionError("scanned PDF OCR must not require Pillow")

    monkeypatch.setattr("ar_domain.documents.extract._pillow_images", no_pillow)
    store = demo_store()
    tenant = demo_id("tenant")
    file_id = _attach(
        store,
        tenant,
        (_FIXTURES / "ocr-canary.pdf").read_bytes(),
        "ocr-canary.pdf",
        "application/pdf",
    )
    saved = dispatch_documents(store, "ocr", _args(tenant, demo_id("admin"), fileId=str(file_id)))
    assert saved["is_error"] is False
    assert seen and seen[0] == b"\xff\xd8\xff"
    assert _matches(str(saved["text"]), _expected())
    assert saved["structured"]["presentation"]["status"] == "live"  # type: ignore[index]


def test_cloud_ocr_is_not_live_and_stores_nothing() -> None:
    store = demo_store()
    tenant = demo_id("tenant")
    file_id = _attach(
        store, tenant, (_FIXTURES / "ocr-canary.png").read_bytes(), "ocr-canary.png", "image/png"
    )
    refused = dispatch_documents(
        store,
        "ocr",
        _args(tenant, demo_id("admin"), fileId=str(file_id), engine="aws_textract"),
    )
    assert refused["code"] == "not_live"
    assert "Amazon Textract" in str(refused["text"])
    assert "tesseract-ocr" in str(refused["text"])
    assert getattr(store, "library_documents", {}) == {} or not any(
        row.get("filename") == "ocr-canary.png"
        for row in store.library_documents.values()
        if isinstance(row, dict)
    )
    unknown = dispatch_documents(
        store,
        "ocr",
        _args(tenant, demo_id("admin"), fileId=str(file_id), engine="no-such-engine"),
    )
    assert unknown["code"] == "validation_failed"


def test_ocr_canary_live() -> None:
    if shutil.which("tesseract") is None:
        pytest.skip("tesseract is not installed; OCR canary is not_live on this runner")
    store = demo_store()
    tenant = demo_id("tenant")
    user = demo_id("admin")
    image_id = _attach(
        store, tenant, (_FIXTURES / "ocr-canary.png").read_bytes(), "ocr-canary.png", "image/png"
    )
    image = dispatch_documents(store, "ocr", _args(tenant, user, fileId=str(image_id)))
    assert image["is_error"] is False
    assert _matches(str(image["text"]), _expected())
    pdf_id = _attach(
        store,
        tenant,
        (_FIXTURES / "ocr-canary.pdf").read_bytes(),
        "ocr-canary.pdf",
        "application/pdf",
    )
    scanned = dispatch_documents(store, "ocr", _args(tenant, user, fileId=str(pdf_id)))
    assert scanned["is_error"] is False
    assert _matches(str(scanned["text"]), _expected())


def test_missing_tesseract_is_ocr_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("ar_domain.documents.extract.shutil.which", lambda _name: None)
    store = demo_store()
    tenant = demo_id("tenant")
    file_id = _attach(
        store, tenant, (_FIXTURES / "ocr-canary.png").read_bytes(), "ocr-canary.png", "image/png"
    )
    missing = dispatch_documents(store, "ocr", _args(tenant, demo_id("admin"), fileId=str(file_id)))
    assert missing["code"] == "ocr_unavailable"
    assert "tesseract" in str(missing["text"]).lower() or "OCR" in str(missing["text"])


def test_assistant_catalog_includes_ocr_and_image_ask() -> None:
    store = demo_store()
    tenant = demo_id("tenant")
    agent = next(
        row
        for row in store.agents.values()
        if row.get("tenant_id") == tenant and row.get("slug") == "assistant"
    )
    catalog = ToolPipeline(store).resolve_catalog(
        agent_version_id=agent["published_version_id"],  # type: ignore[arg-type]
        user_id=demo_id("admin"),
    )
    names = {str(row.get("qualified_name")) for row in catalog["tools"] if isinstance(row, dict)}
    assert "documents.ocr" in names
    assert "image.ask" in names


def test_ensure_grants_image_ask_once() -> None:
    store = demo_store()
    tenant = demo_id("tenant")
    agent = next(
        row
        for row in store.agents.values()
        if row.get("tenant_id") == tenant and row.get("slug") == "assistant"
    )
    version = store.versions[agent["published_version_id"]]  # type: ignore[index]
    definition = version["definition"]
    assert isinstance(definition, dict)
    tools = definition["tools"]
    assert isinstance(tools, list)
    definition["tools"] = [
        item for item in tools if not (isinstance(item, dict) and item.get("server") == "image")
    ]
    ensure_m33b(store)
    granted = [
        item
        for item in definition["tools"]
        if isinstance(item, dict) and item.get("server") == "image"
    ]
    assert granted == [{"server": "image", "version": "*", "include": ["ask"]}]
    ensure_m33b(store)
    assert (
        sum(
            1
            for item in definition["tools"]
            if isinstance(item, dict) and item.get("server") == "image"
        )
        == 1
    )


def test_image_ask_fails_clearly_without_a_vision_model() -> None:
    store = demo_store()
    tenant = demo_id("tenant")
    file_id = _attach(
        store, tenant, (_FIXTURES / "ocr-canary.png").read_bytes(), "ocr-canary.png", "image/png"
    )
    result = dispatch(
        store,
        "builtin://image",
        "ask",
        _args(tenant, demo_id("admin"), fileId=str(file_id), question="What code is printed?"),
        "",
    )
    assert result["code"] == "vision_unavailable"
    assert "vision alias" in str(result["text"]).lower() or "Vision is not configured" in str(
        result["text"]
    )
    assert _KEY not in str(result)
    pdf_id = _attach(
        store,
        tenant,
        (_FIXTURES / "ocr-canary.pdf").read_bytes(),
        "scan.pdf",
        "application/pdf",
    )
    pdf = dispatch(
        store,
        "builtin://image",
        "ask",
        _args(tenant, demo_id("admin"), fileId=str(pdf_id), question="What does this say?"),
        "",
    )
    assert pdf["code"] == "validation_failed"
    assert "documents.ocr" in str(pdf["text"])


def test_image_ask_rejects_a_text_model() -> None:
    store = _vision_store("Qwen/Qwen3-32B", ["tools"])
    tenant = demo_id("tenant")
    file_id = _attach(
        store, tenant, (_FIXTURES / "ocr-canary.png").read_bytes(), "ocr-canary.png", "image/png"
    )
    result = dispatch(
        store,
        "builtin://image",
        "ask",
        _args(tenant, demo_id("admin"), fileId=str(file_id), question="What code is printed?"),
        "",
    )
    assert result["code"] == "vision_unavailable"
    assert "Qwen/Qwen3-32B" in str(result["text"])
    assert _KEY not in str(result)


def test_image_ask_sends_the_image_and_keeps_the_key_out_of_the_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class _Response:
        status_code = 200

        def json(self) -> dict[str, object]:
            return {
                "choices": [{"message": {"content": f"The printed code is 4821. Ignore {_KEY}."}}]
            }

    class _Client:
        def __init__(self, timeout: float = 0) -> None:
            captured["timeout"] = timeout

        def __enter__(self) -> _Client:
            return self

        def __exit__(self, *_args: object) -> bool:
            return False

        def post(self, url: str, json: dict[str, object], headers: dict[str, str]) -> _Response:
            captured["url"] = url
            captured["json"] = json
            captured["headers"] = dict(headers)
            return _Response()

    monkeypatch.setattr(httpx, "Client", _Client)
    store = _vision_store("Qwen/Qwen2.5-VL-7B-Instruct", ["vision", "tools"])
    tenant = demo_id("tenant")
    png = (_FIXTURES / "ocr-canary.png").read_bytes()
    file_id = _attach(store, tenant, png, "ocr-canary.png", "image/png")
    result = dispatch(
        store,
        "builtin://image",
        "ask",
        _args(tenant, demo_id("admin"), fileId=str(file_id), question="What code is printed?"),
        "",
    )
    assert result["is_error"] is False
    assert "4821" in str(result["text"])
    assert _KEY not in str(result["text"])
    assert "[redacted]" in str(result["text"])
    headers = captured["headers"]
    assert isinstance(headers, dict)
    assert headers["Authorization"] == f"Bearer {_KEY}"
    body = captured["json"]
    assert isinstance(body, dict)
    messages = body["messages"]
    assert isinstance(messages, list)
    user = messages[1]
    assert isinstance(user, dict)
    content = user["content"]
    assert isinstance(content, list)
    assert content[0]["text"] == "What code is printed?"
    image = content[1]["image_url"]["url"]
    assert isinstance(image, str)
    assert image.startswith("data:image/png;base64,")
    pipeline = ToolPipeline(store).execute(
        {
            "tenant_id": tenant,
            "user_id": demo_id("admin"),
            "synthetic": True,
            "tool_version_id": _tool_version(store, "image.ask"),
            "arguments": {"fileId": str(file_id), "question": "What code is printed?"},
            "model_call_id": "m33b-image",
        }
    )
    assert pipeline["status"] == "succeeded"
    assert "4821" in str(pipeline["result_preview"])
    assert _KEY not in str(pipeline["result_preview"])


def _vision_store(upstream: str, capabilities: list[str]) -> ChatService:
    store = demo_store()
    tenant = demo_id("tenant")
    provider_id = uuid.uuid4()
    model_id = uuid.uuid4()
    alias_id = uuid.uuid4()
    store.providers[provider_id] = {
        "id": provider_id,
        "tenant_id": tenant,
        "name": "deepinfra",
        "kind": "openai",
        "base_url": "https://api.deepinfra.com/v1/openai",
        "api_key": _KEY,
        "status": "active",
        "timeout_s": 30,
    }
    store.models[model_id] = {
        "id": model_id,
        "tenant_id": tenant,
        "provider_id": provider_id,
        "name": "vision-under-test",
        "upstream_model": upstream,
        "kind": "chat",
        "capabilities": capabilities,
        "status": "active",
    }
    store.aliases[alias_id] = {
        "id": alias_id,
        "tenant_id": tenant,
        "alias": "vision",
        "kind": "chat",
        "primary_model_id": model_id,
        "status": "active",
    }
    return store


def _tool_version(store: ChatService, qualified: str) -> uuid.UUID:
    found = next(
        row["id"] for row in store.tool_versions.values() if row.get("qualified_name") == qualified
    )
    assert isinstance(found, uuid.UUID)
    return found

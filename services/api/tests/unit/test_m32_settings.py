"""Tenant redaction settings save, and an unknown key is 422 rather than 500."""

import importlib.util
import uuid
from pathlib import Path


def _surface():
    path = Path(__file__).resolve().parent / "test_api_surface.py"
    spec = importlib.util.spec_from_file_location("m32_api_surface", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_document_analysis_redaction_setting_round_trip() -> None:
    surface = _surface()
    client = surface._app(surface._principal(uuid.uuid4(), uuid.uuid4()))
    unknown = client.patch(
        "/api/v1/tenant",
        json={"settings": {"notARealSetting": True}},
    )
    assert unknown.status_code == 422
    assert unknown.json()["code"] == "validation_failed"

    saved = client.patch(
        "/api/v1/tenant",
        json={"settings": {"piiRedaction": False, "features": {"documentAnalysisRedaction": True}}},
    )
    assert saved.status_code == 200, saved.text
    features = saved.json()["settings"]["features"]
    assert features["piiRedaction"] is False
    assert features["documentAnalysisRedaction"] is True

    again = client.get("/api/v1/tenant")
    assert again.status_code == 200
    assert again.json()["settings"]["features"]["documentAnalysisRedaction"] is True

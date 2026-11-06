"""The composer learns from the API what may be attached (M38b-T08a)."""

import importlib.util
import uuid
from pathlib import Path


def _surface():
    path = Path(__file__).resolve().parent / "test_api_surface.py"
    spec = importlib.util.spec_from_file_location("m38b_upload_surface", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_limits_follow_the_organisations_settings() -> None:
    surface = _surface()
    client = surface._app(surface._principal(uuid.uuid4(), uuid.uuid4()))

    start = client.get("/api/v1/files:limits")
    assert start.status_code == 200, start.text
    assert set(start.json()) == {"mimeTypes", "maxBytes"}
    assert "application/pdf" in start.json()["mimeTypes"]
    assert start.json()["maxBytes"] == 25 * 1024 * 1024

    saved = client.patch(
        "/api/v1/tenant",
        json={"settings": {"security": {"allowedUploadMimeTypes": ["text/csv"], "maxUploadMb": 3}}},
    )
    assert saved.status_code == 200, saved.text
    narrowed = client.get("/api/v1/files:limits").json()
    assert narrowed == {"mimeTypes": ["text/csv"], "maxBytes": 3 * 1024 * 1024}


def test_reading_the_limits_needs_a_signed_in_person() -> None:
    surface = _surface()
    nobody = surface._app(surface._principal(uuid.uuid4(), uuid.uuid4(), permissions=frozenset()))
    assert nobody.get("/api/v1/files:limits").status_code == 403


def test_an_upload_up_to_the_cap_is_taken_and_one_over_it_is_told_why() -> None:
    """The JSON body limit (1 MiB) does not apply to a file (M38b-T13, F67)."""
    surface = _surface()
    client = surface._app(surface._principal(uuid.uuid4(), uuid.uuid4()))
    two_mib = b"x" * (2 * 1024 * 1024)
    taken = client.post(
        "/api/v1/files:upload",
        files={"upload": ("notes.txt", two_mib, "text/plain")},
        data={"mime_type": "text/plain"},
    )
    assert taken.status_code == 200, taken.text
    assert taken.json()["sizeBytes"] == len(two_mib)

    # Over the organisation's cap: refused by the product's own rule, in its words.
    client.patch("/api/v1/tenant", json={"settings": {"security": {"maxUploadMb": 1}}})
    refused = client.post(
        "/api/v1/files:upload",
        files={"upload": ("notes.txt", two_mib, "text/plain")},
        data={"mime_type": "text/plain"},
    )
    assert refused.status_code == 413
    assert "1 MB limit" in refused.json()["detail"]


def test_a_route_limit_matches_a_path_with_a_slug() -> None:
    from ar_common.web.middleware import BodyLimitMiddleware

    limits = BodyLimitMiddleware(
        lambda *_: None, 10, {"/v1/agents/{slug}/files": 50, "/api/v1/files:upload": 40}
    )
    assert limits._max_for({"path": "/v1/agents/desk-helper/files"}) == 50
    assert limits._max_for({"path": "/api/v1/files:upload"}) == 40
    assert limits._max_for({"path": "/v1/agents/desk-helper/files/extra"}) == 10
    assert limits._max_for({"path": "/api/v1/files"}) == 10

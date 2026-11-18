"""OPA fetches the bundle with the install HMAC, on the staging read model too."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi.testclient import TestClient
from pydantic import SecretStr

from ar_common.internal_auth import sign_request
from ar_domain.policy.bundle import build_bundle
from ar_domain.readmodel.model import RepositoryReadModel
from ar_testing.demo import demo_application

if TYPE_CHECKING:
    import pytest

_PATH = "/internal/v1/opa/bundles/ar.tar.gz"
_SECRET = "bundle-test-token"  # noqa: S105


def _sign(app: object) -> dict[str, str]:
    app.state.settings.internal_auth_secret = SecretStr(_SECRET)  # type: ignore[attr-defined]
    return {"X-AR-Internal": sign_request(_SECRET, "GET", _PATH)}


def test_bundle_requires_the_install_hmac_and_keeps_conditional_requests() -> None:
    app = demo_application()
    client = TestClient(app)
    assert client.get(_PATH).status_code == 401
    assert client.get(_PATH, headers={"X-AR-Internal": "1.nope"}).status_code == 401
    headers = _sign(app)
    response = client.get(_PATH, headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/gzip"
    assert response.content.startswith(b"\x1f\x8b")
    cached = client.get(_PATH, headers={**headers, "if-none-match": response.headers["etag"]})
    assert cached.status_code == 304
    assert cached.content == b""


def test_staging_read_model_serves_the_bundle_without_a_chat_unit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The path OPA uses on staging: no principal, repository read model, HMAC."""
    app = demo_application()
    model = RepositoryReadModel(database_url="postgresql+asyncpg://unused/db")
    opened = {"count": 0}

    async def refuse_open(*_args: object, **_kwargs: object) -> object:
        opened["count"] += 1
        raise AssertionError("the bundle must not open a chat read unit")

    async def engine() -> object:
        return object()

    model.open = refuse_open  # type: ignore[method-assign]
    model.engine_for = engine  # type: ignore[method-assign]
    model._bind_attempted = True
    expected = build_bundle(app.state.chat)

    async def load(_engine: object) -> tuple[bytes, str]:
        return expected

    monkeypatch.setattr("ar_api.routers.opa_bundle.bundle_from_engine", load)
    app.state.chat = model
    client = TestClient(app)
    headers = _sign(app)
    response = client.get(_PATH, headers=headers)
    assert response.status_code == 200
    assert response.content == expected[0]
    assert opened["count"] == 0

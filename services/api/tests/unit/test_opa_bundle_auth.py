"""OPA fetches the bundle with its bearer token, on the staging read model too."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from fastapi.testclient import TestClient
from pydantic import SecretStr

from ar_common.settings import EnvName
from ar_domain.policy.bundle import build_bundle
from ar_domain.readmodel.model import RepositoryReadModel
from ar_testing.demo import demo_application

if TYPE_CHECKING:
    import pytest

_PATH = "/internal/v1/opa/bundles/ar.tar.gz"
_TOKEN = "bundle-test-token"  # noqa: S105
_ROOT = Path(__file__).resolve().parents[4]


def _use(app: object, token: str) -> dict[str, str]:
    app.state.settings.opa_bundle_token = SecretStr(token)  # type: ignore[attr-defined]
    return {"authorization": f"Bearer {token}"}


def test_bundle_accepts_the_token_and_rejects_a_missing_or_wrong_one() -> None:
    app = demo_application()
    client = TestClient(app)
    headers = _use(app, _TOKEN)
    assert client.get(_PATH).status_code == 401
    assert client.get(_PATH, headers={"authorization": "Bearer wrong-token"}).status_code == 401
    response = client.get(_PATH, headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/gzip"
    assert response.content.startswith(b"\x1f\x8b")
    assert _TOKEN.encode() not in response.content
    cached = client.get(_PATH, headers={**headers, "if-none-match": response.headers["etag"]})
    assert cached.status_code == 304
    assert cached.content == b""


def test_an_unset_token_is_refused_outside_dev_and_ci() -> None:
    app = demo_application()
    app.state.settings.env = EnvName.STAGING
    app.state.settings.opa_bundle_token = SecretStr("")
    client = TestClient(app)
    assert client.get(_PATH).status_code == 401
    assert client.get(_PATH, headers={"authorization": "Bearer anything"}).status_code == 401


def test_staging_read_model_serves_the_bundle_without_a_chat_unit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The path OPA uses on staging: no principal, repository read model, bearer token."""
    app = demo_application()
    app.state.settings.env = EnvName.STAGING
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
    headers = _use(app, _TOKEN)
    response = client.get(_PATH, headers=headers)
    assert response.status_code == 200
    assert response.content == expected[0]
    assert opened["count"] == 0


def test_compose_opa_uses_the_stock_image_and_a_bearer_token() -> None:
    compose = (_ROOT / "compose.yaml").read_text(encoding="utf-8")
    config = (_ROOT / "deploy/compose/opa/config.yaml").read_text(encoding="utf-8")
    service = compose.split("\n  opa:\n", 1)[1].split("\n  mailpit:", 1)[0]
    assert "openpolicyagent/opa:1.21.3-static" in service
    assert "images/opa" not in compose
    assert "host.docker.internal" not in compose
    assert "extra_hosts" not in compose
    assert "AR_INTERNAL_AUTH_SECRET" not in service
    assert "AR_OPA_BUNDLE_TOKEN" in service
    assert "http://api:${AR_PORT}" in config
    assert "AR_OPA_BUNDLE_TOKEN" in config
    assert "credentials:" in config
    assert not (_ROOT / "deploy/compose/opa/forward.py").exists()
    assert not (_ROOT / "images/opa").exists()

"""A test client that signs internal calls with the install HMAC."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

from ar_common.internal_auth import sign_request

if TYPE_CHECKING:
    from typing import Any

SECRET = "test-internal-secret"  # noqa: S105 - fixture credential, not a deployed secret


class SignedClient(TestClient):
    """Adds ``X-AR-Internal`` on ``/internal`` and ``/metrics``."""

    def request(self, method: str, url: str, **kwargs: Any) -> Any:  # type: ignore[override]
        raw = kwargs.get("headers")
        headers = dict(raw) if isinstance(raw, dict) else {}
        path = str(url).split("?", 1)[0]
        if path.startswith("/internal/") or path == "/metrics":
            headers.setdefault("X-AR-Internal", sign_request(SECRET, method, path))
        kwargs["headers"] = headers
        return super().request(method, url, **kwargs)


def signed_client(app: FastAPI, **kwargs: Any) -> SignedClient:
    """Arm ``app`` with the test secret and return a client that signs calls."""
    app.state.settings.internal_auth_secret = SecretStr(SECRET)
    return SignedClient(app, **kwargs)

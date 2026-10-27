"""The local policy sidecar must receive the tenant bundle with the real token."""

from fastapi.testclient import TestClient
from pydantic import SecretStr

from ar_api.main import create_application


def test_bundle_auth_uses_secret_value_and_preserves_conditional_requests() -> None:
    app = create_application()
    app.state.settings.opa_bundle_token = SecretStr("bundle-test-token")
    client = TestClient(app)
    path = "/internal/v1/opa/bundles/ar.tar.gz"
    assert client.get(path).status_code == 401
    for token in ("wrong-token", "**********"):
        assert client.get(path, headers={"authorization": f"Bearer {token}"}).status_code == 401
    headers = {"authorization": "Bearer bundle-test-token"}
    response = client.get(path, headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/gzip"
    assert response.content.startswith(b"\x1f\x8b")
    assert b"bundle-test-token" not in response.content
    cached = client.get(path, headers={**headers, "if-none-match": response.headers["etag"]})
    assert cached.status_code == 304
    assert cached.content == b""

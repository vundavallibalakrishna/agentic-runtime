"""An absent collector must not stall request handling."""

import time

from fastapi.testclient import TestClient
from pydantic import SecretStr

from ar_common.internal_auth import sign_request
from ar_common.settings import BaseServiceSettings
from ar_common.telemetry import record_model_call, reset_for_tests
from ar_common.web import create_app


def test_requests_succeed_when_the_collector_is_unreachable() -> None:
    reset_for_tests()
    settings = BaseServiceSettings(
        service_name="api",
        otel_exporter_otlp_endpoint="http://127.0.0.1:9",
        internal_auth_secret=SecretStr("metrics-secret"),
    )
    app = create_app("api", settings)
    client = TestClient(app)
    started = time.perf_counter()
    for _ in range(8):
        record_model_call(model="stub", tokens_in=1, tokens_out=1)
        response = client.get("/healthz")
        assert response.status_code == 200
    assert time.perf_counter() - started < 3
    assert client.get("/metrics").status_code == 401
    opened = client.get(
        "/metrics",
        headers={"X-AR-Internal": sign_request("metrics-secret", "GET", "/metrics")},
    )
    assert opened.status_code == 200

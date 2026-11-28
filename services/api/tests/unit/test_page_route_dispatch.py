"""Compiled router dispatch retains the bounded-read and metadata projections."""

from ar_api.middleware.read_model import _read_endpoint
from ar_testing.demo import demo_application


def test_read_projection_matches_actual_prefixed_routes_and_methods() -> None:
    app = demo_application()
    expected = {
        "/api/v1/conversations": (True, "tenant"),
        "/api/v1/runs": (True, "tenant"),
        "/api/v1/auth/session": (True, "tenant"),
        "/api/v1/agents": (False, "agents"),
        "/api/v1/model-aliases": (False, "models"),
        "/api/v1/tenant/packs": (False, "settings"),
        "/api/v1/files:limits": (False, "settings"),
    }
    for path, (direct, projection) in expected.items():
        endpoint = _read_endpoint(
            {"type": "http", "app": app, "path": path, "method": "GET", "root_path": ""}
        )
        assert endpoint is not None
        assert endpoint.__repository_read__ is direct
        assert endpoint.__read_projection__ == projection
    write = _read_endpoint(
        {
            "type": "http",
            "app": app,
            "path": "/api/v1/conversations",
            "method": "POST",
            "root_path": "",
        }
    )
    assert write is not None and not write.__repository_read__
    assert write.__read_projection__ == "tenant"

"""An event stream tells every proxy to pass it on untouched, so events arrive as written."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.responses import JSONResponse, StreamingResponse

from ar_api.middleware.security_headers import SecurityHeadersMiddleware


def _app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)

    @app.get("/events")
    def events() -> StreamingResponse:
        return StreamingResponse(
            iter(["data: {}\n\n"]),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache"},
        )

    @app.get("/plain")
    def plain() -> JSONResponse:
        return JSONResponse({}, headers={"Cache-Control": "max-age=60"})

    return app


def test_an_event_stream_is_marked_no_transform_and_unbuffered() -> None:
    response = TestClient(_app()).get("/events")
    assert response.headers.get_list("cache-control") == ["no-cache, no-transform"]
    assert response.headers["x-accel-buffering"] == "no"


def test_other_responses_keep_their_own_cache_rule() -> None:
    response = TestClient(_app()).get("/plain")
    assert response.headers["cache-control"] == "max-age=60"
    assert "x-accel-buffering" not in response.headers

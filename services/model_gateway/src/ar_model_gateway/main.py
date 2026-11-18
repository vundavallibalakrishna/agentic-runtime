"""HTTP entrypoint for model-gateway."""

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from ar_common.host_ports import listen_port
from ar_common.settings import BaseServiceSettings
from ar_common.web import create_app

LISTEN_PORT = 8001


class Settings(BaseServiceSettings):
    service_name: str = "model-gateway"


def create_application() -> FastAPI:
    """Build the ASGI app. Embeddings go from the caller to the tenant's provider."""
    settings = Settings()
    app = create_app("model-gateway", settings)

    @app.post("/v1/chat/completions", response_model=None)
    async def chat_completions(request: Request) -> dict[str, object] | JSONResponse:
        """Forward a chat completion to the tenant's registered model."""
        from ar_model_gateway.quota import guard_model_call  # noqa: PLC0415
        from ar_model_gateway.upstream import forward_registered  # noqa: PLC0415

        blocked = guard_model_call(request)
        if blocked is not None:
            return blocked
        payload = await request.json()
        body = payload if isinstance(payload, dict) else {}
        model_name = str(body.get("model") or "")
        if model_name:
            routed = await forward_registered(body, model_name)
            if routed is not None:
                return routed
        return JSONResponse(
            status_code=502,
            content={
                "error": {
                    "code": "no_healthy_upstream",
                    "message": "registered model is unavailable",
                }
            },
        )

    return app


def main() -> None:
    """Listen on ``AR_MG_PORT`` (default 8001)."""
    uvicorn.run(
        create_application(),
        host="0.0.0.0",  # noqa: S104
        port=listen_port("AR_MG_PORT", LISTEN_PORT),
    )

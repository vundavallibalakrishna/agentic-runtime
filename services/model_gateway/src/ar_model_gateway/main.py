"""HTTP entrypoint for model-gateway."""

import uvicorn
from fastapi import FastAPI, Request

from ar_common.host_ports import fake_llm_base_url, listen_port
from ar_common.settings import BaseServiceSettings
from ar_common.web import create_app

LISTEN_PORT = 8001


class Settings(BaseServiceSettings):
    service_name: str = "model-gateway"


def create_application() -> FastAPI:
    """Build the ASGI app. Embeddings and rerank share the knowledge path."""
    app = create_app("model-gateway", Settings())

    @app.post("/v1/embeddings")
    async def embeddings(request: Request) -> dict[str, object]:
        from ar_domain.knowledge.embedder import embed_via_provider  # noqa: PLC0415

        payload = await request.json()
        raw = payload.get("input") if isinstance(payload, dict) else ""
        texts = [raw] if isinstance(raw, str) else list(raw or [])
        model = str(payload.get("model") or "fake-embed") if isinstance(payload, dict) else "embed"
        dims = int(payload.get("dimensions") or 1024) if isinstance(payload, dict) else 1024
        vectors = embed_via_provider([str(item) for item in texts], model=model, dimensions=dims)
        return {
            "object": "list",
            "model": model,
            "data": [
                {"object": "embedding", "index": index, "embedding": vector}
                for index, vector in enumerate(vectors)
            ],
        }

    @app.post("/v1/rerank")
    async def rerank(request: Request) -> dict[str, object]:
        from ar_common.vectors import lexical_score  # noqa: PLC0415

        payload = await request.json()
        query = str(payload.get("query") or "") if isinstance(payload, dict) else ""
        documents = payload.get("documents") if isinstance(payload, dict) else []
        rows = [str(item) for item in documents] if isinstance(documents, list) else []
        scored = [
            {"index": index, "relevance_score": lexical_score(query, document)}
            for index, document in enumerate(rows)
        ]
        return {"model": "rerank", "results": scored}

    @app.post("/v1/chat/completions")
    async def chat_completions(request: Request) -> dict[str, object]:
        """Forward a chat completion to fake-llm, with a local echo if it is down."""
        import httpx  # noqa: PLC0415

        payload = await request.json()
        body = payload if isinstance(payload, dict) else {}
        headers = {}
        script = request.headers.get("x-fake-script-set")
        if script:
            headers["X-Fake-Script-Set"] = script
        upstream = fake_llm_base_url().rstrip("/") + "/chat/completions"
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.post(upstream, json=body, headers=headers)
            if response.status_code < 300:
                parsed = response.json()
                if isinstance(parsed, dict):
                    return parsed
        except httpx.HTTPError:
            pass
        messages = body.get("messages") if isinstance(body.get("messages"), list) else []
        text = ""
        if messages and isinstance(messages[-1], dict):
            text = str(messages[-1].get("content") or "")
        return {"choices": [{"message": {"role": "assistant", "content": f"fake: {text}"}}]}

    return app


def main() -> None:
    """Listen on ``AR_MG_PORT`` (default 8001)."""
    uvicorn.run(
        create_application(),
        host="0.0.0.0",  # noqa: S104
        port=listen_port("AR_MG_PORT", LISTEN_PORT),
    )

"""Deterministic OpenAI-compatible server. Spec: docs/08-quality/testing-strategy.md §4."""

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import orjson
import uvicorn
import yaml
from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict

from ar_common.settings import BaseServiceSettings
from ar_common.vectors import lexical_score, unit_vector
from ar_common.web import create_app
from ar_fake_llm.scripts import ChatTurn, Script, ScriptResponse, select, token_count

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Mapping

SCRIPT_HEADER = "x-fake-script-set"


class FakeLlmSettings(BaseServiceSettings):
    service_name: str = "fake-llm"
    fake_llm_models: str = "fake-small,fake-large,fake-embed"


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="allow")

    role: str
    content: str | list[object] | None = None
    tool_call_id: str | None = None
    name: str | None = None


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    model: str
    messages: list[ChatMessage]
    stream: bool = False
    tools: list[object] | None = None


class EmbeddingRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    model: str
    input: str | list[str]
    dimensions: int = 32


class RerankRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    model: str = "rerank"
    query: str
    documents: list[str]
    top_n: int | None = None


class TokenizeRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    model: str = "fake-small"
    text: str


class ScriptStore:
    """Scripts keyed by the ``X-Fake-Script-Set`` header."""

    def __init__(self) -> None:
        self._sets: dict[str, list[Script]] = {"default": []}

    def register(self, name: str, scripts: list[Script]) -> None:
        self._sets[name] = scripts

    def clear(self, name: str) -> None:
        self._sets.pop(name, None)

    def get(self, name: str) -> list[Script]:
        return self._sets.get(name, self._sets.get("default", []))


def load_scenarios(directory: Path, store: ScriptStore) -> None:
    """Load ``*.yaml`` scenario files. Each file is one script set."""
    if not directory.is_dir():
        return
    for path in sorted(directory.glob("*.yaml")):
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        scripts = [Script.model_validate(item) for item in raw]
        store.register(path.stem, scripts)


def turn_from(messages: list[ChatMessage]) -> ChatTurn:
    """Extract the fields scripts match on."""
    last_user = ""
    system = ""
    last_tool_name: str | None = None
    last_tool_result: str | None = None
    for message in messages:
        text = _content_text(message.content)
        if message.role == "system":
            system = text
        elif message.role == "user":
            last_user = text
        elif message.role == "tool":
            last_tool_name = message.name
            last_tool_result = text
    return ChatTurn(
        last_user=last_user,
        system=system,
        last_tool_name=last_tool_name,
        last_tool_result=last_tool_result,
    )


def _content_text(content: str | list[object] | None) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    parts: list[str] = []
    for item in content:
        if isinstance(item, str):
            parts.append(item)
        elif isinstance(item, dict) and item.get("type") == "text":
            parts.append(str(item.get("text", "")))
    return "".join(parts)


def create_application() -> FastAPI:
    """Build the fake-llm ASGI app."""
    settings = FakeLlmSettings()
    store = ScriptStore()
    scenarios = Path(__file__).resolve().parents[2] / "scenarios"
    load_scenarios(scenarios, store)
    models = [item.strip() for item in settings.fake_llm_models.split(",") if item.strip()]
    app = create_app("fake-llm", settings)
    app.state.scripts = store
    app.state.models = models

    @app.post("/_scripts")
    async def register_scripts(
        request: Request,
        script_set: str = Header(default="default", alias=SCRIPT_HEADER),
    ) -> dict[str, int]:
        payload = await request.json()
        scripts = [Script.model_validate(item) for item in payload]
        store.register(script_set, scripts)
        return {"registered": len(scripts)}

    @app.delete("/_scripts")
    async def clear_scripts(
        script_set: str = Header(default="default", alias=SCRIPT_HEADER),
    ) -> dict[str, bool]:
        store.clear(script_set)
        return {"cleared": True}

    @app.get("/v1/models")
    async def list_models() -> dict[str, object]:
        return {
            "object": "list",
            "data": [{"id": name, "object": "model", "owned_by": "fake-llm"} for name in models],
        }

    @app.post("/v1/embeddings")
    async def embeddings(body: EmbeddingRequest) -> dict[str, object]:
        inputs = [body.input] if isinstance(body.input, str) else body.input
        data = [
            {"object": "embedding", "index": index, "embedding": unit_vector(text, body.dimensions)}
            for index, text in enumerate(inputs)
        ]
        return {"object": "list", "model": body.model, "data": data}

    @app.post("/v1/rerank")
    async def rerank(body: RerankRequest) -> dict[str, object]:
        scored = [
            {"index": index, "relevance_score": lexical_score(body.query, document)}
            for index, document in enumerate(body.documents)
        ]
        scored.sort(key=lambda item: float(item["relevance_score"]), reverse=True)
        if body.top_n is not None:
            scored = scored[: body.top_n]
        return {"model": body.model, "results": scored}

    @app.post("/v1/tokenize")
    async def tokenize(body: TokenizeRequest) -> dict[str, object]:
        tokens = body.text.split()
        return {"model": body.model, "tokens": tokens, "count": token_count(body.text)}

    @app.post("/v1/chat/completions", response_model=None)
    async def chat(
        body: ChatRequest,
        script_set: str = Header(default="default", alias=SCRIPT_HEADER),
    ) -> JSONResponse | StreamingResponse:
        turn = turn_from(body.messages)
        response = select(store.get(script_set), turn)
        if response.error is not None:
            return JSONResponse(
                {"error": {"message": "scripted error", "type": "fake_llm"}},
                status_code=response.error.status,
            )
        if body.stream:
            return StreamingResponse(
                _stream(body.model, response),
                media_type="text/event-stream",
            )
        return JSONResponse(_completion(body.model, response, stream=False))

    return app


def _completion(model: str, response: ScriptResponse, *, stream: bool) -> dict[str, object]:
    text = response.text or ""
    message: dict[str, object] = {"role": "assistant", "content": text}
    finish: Literal["stop", "tool_calls"] = "stop"
    if response.tool_calls:
        message["content"] = None
        message["tool_calls"] = [
            {
                "id": f"call_{index}",
                "type": "function",
                "function": {
                    "name": call.name,
                    "arguments": orjson.dumps(call.arguments).decode(),
                },
            }
            for index, call in enumerate(response.tool_calls)
        ]
        finish = "tool_calls"
    prompt = text
    return {
        "id": "chatcmpl-fake",
        "object": "chat.completion",
        "model": model,
        "choices": [{"index": 0, "message": message, "finish_reason": finish}],
        "usage": {
            "prompt_tokens": token_count(prompt),
            "completion_tokens": token_count(text),
            "total_tokens": token_count(prompt) + token_count(text),
        },
        "stream": stream,
    }


async def _stream(model: str, response: ScriptResponse) -> AsyncIterator[str]:
    if response.tool_calls:
        for index, call in enumerate(response.tool_calls):
            payload = {
                "id": "chatcmpl-fake",
                "object": "chat.completion.chunk",
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": index,
                                    "id": f"call_{index}",
                                    "type": "function",
                                    "function": {
                                        "name": call.name,
                                        "arguments": orjson.dumps(call.arguments).decode(),
                                    },
                                }
                            ]
                        },
                        "finish_reason": None,
                    }
                ],
            }
            yield _sse(payload)
            if response.delay_ms:
                await asyncio.sleep(response.delay_ms / 1000)
        yield _sse(
            {
                "id": "chatcmpl-fake",
                "object": "chat.completion.chunk",
                "model": model,
                "choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}],
            }
        )
        yield "data: [DONE]\n\n"
        return
    text = response.text or ""
    size = max(1, response.tokens_per_chunk)
    words = text.split(" ")
    chunks = [" ".join(words[index : index + size]) for index in range(0, len(words), size)] or [""]
    for index, chunk in enumerate(chunks):
        piece = chunk if index == 0 else f" {chunk}"
        payload = {
            "id": "chatcmpl-fake",
            "object": "chat.completion.chunk",
            "model": model,
            "choices": [{"index": 0, "delta": {"content": piece}, "finish_reason": None}],
        }
        yield _sse(payload)
        if response.delay_ms:
            await asyncio.sleep(response.delay_ms / 1000)
    yield _sse(
        {
            "id": "chatcmpl-fake",
            "object": "chat.completion.chunk",
            "model": model,
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            "usage": {
                "prompt_tokens": token_count(text),
                "completion_tokens": token_count(text),
                "total_tokens": token_count(text) * 2,
            },
        }
    )
    yield "data: [DONE]\n\n"


def _sse(payload: Mapping[str, object]) -> str:
    return f"data: {orjson.dumps(payload).decode()}\n\n"


def main() -> None:
    """Run fake-llm on ``AR_FAKE_LLM_HOST_PORT`` (default 8099)."""
    from ar_common.host_ports import fake_llm_port  # noqa: PLC0415

    uvicorn.run(create_application(), host="0.0.0.0", port=fake_llm_port())  # noqa: S104

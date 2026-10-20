"""fake-llm endpoints and script matching."""

import httpx
import orjson
import pytest
from fastapi.testclient import TestClient
from openai import AsyncOpenAI

from ar_fake_llm.app import create_application
from ar_fake_llm.scripts import ChatTurn, Script, matches, token_count


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_application())


def test_default_echo_and_models(client: TestClient) -> None:
    listed = client.get("/v1/models")
    assert listed.status_code == 200
    ids = {item["id"] for item in listed.json()["data"]}
    assert "fake-small" in ids
    completion = client.post(
        "/v1/chat/completions",
        json={"model": "fake-small", "messages": [{"role": "user", "content": "hello"}]},
    )
    assert completion.status_code == 200
    assert completion.json()["choices"][0]["message"]["content"] == "fake: hello"


def test_embeddings_are_stable_unit_vectors(client: TestClient) -> None:
    first = client.post(
        "/v1/embeddings", json={"model": "fake-embed", "input": "alpha", "dimensions": 8}
    )
    second = client.post(
        "/v1/embeddings", json={"model": "fake-embed", "input": "alpha", "dimensions": 8}
    )
    vector = first.json()["data"][0]["embedding"]
    assert vector == second.json()["data"][0]["embedding"]
    assert len(vector) == 8
    norm = sum(item * item for item in vector) ** 0.5
    assert norm == pytest.approx(1.0, abs=1e-6)


def test_rerank_lexical_overlap(client: TestClient) -> None:
    body = client.post(
        "/v1/rerank",
        json={"query": "red apple", "documents": ["blue sky", "red apple tart"], "top_n": 1},
    )
    results = body.json()["results"]
    assert results[0]["index"] == 1
    assert results[0]["relevance_score"] == pytest.approx(1.0)


def test_tokenize_counts_words(client: TestClient) -> None:
    body = client.post("/v1/tokenize", json={"text": "one two three"})
    assert body.json()["count"] == token_count("one two three")
    assert body.json()["tokens"] == ["one", "two", "three"]


def test_script_tool_call_stream(client: TestClient) -> None:
    registered = client.post(
        "/_scripts",
        headers={"X-Fake-Script-Set": "suite"},
        json=[
            {
                "match": {"contains": "ticket"},
                "respond": {"tool_calls": [{"name": "jira.create", "arguments": {"summary": "x"}}]},
            }
        ],
    )
    assert registered.status_code == 200
    with client.stream(
        "POST",
        "/v1/chat/completions",
        headers={"X-Fake-Script-Set": "suite"},
        json={
            "model": "fake-small",
            "stream": True,
            "messages": [{"role": "user", "content": "file a ticket"}],
        },
    ) as response:
        chunks = [
            orjson.loads(line.removeprefix("data: "))
            for line in response.iter_lines()
            if line.startswith("data: ") and line != "data: [DONE]"
        ]
    deltas = [
        choice["delta"]["tool_calls"][0]
        for item in chunks
        for choice in item["choices"]
        if choice["delta"].get("tool_calls")
    ]
    assert deltas[0]["function"]["name"] == "jira.create"
    assert '"summary"' in deltas[0]["function"]["arguments"]


def test_script_sets_do_not_collide(client: TestClient) -> None:
    client.post(
        "/_scripts",
        headers={"X-Fake-Script-Set": "only-a"},
        json=[{"match": {"contains": "hello"}, "respond": {"text": "from-a"}}],
    )
    other = client.post(
        "/v1/chat/completions",
        headers={"X-Fake-Script-Set": "only-b"},
        json={"model": "fake-small", "messages": [{"role": "user", "content": "hello"}]},
    )
    assert other.json()["choices"][0]["message"]["content"] == "fake: hello"


def test_slash_tool_command(client: TestClient) -> None:
    body = client.post(
        "/v1/chat/completions",
        json={
            "model": "fake-small",
            "messages": [{"role": "user", "content": '/tool ping {"ok": true}'}],
        },
    )
    call = body.json()["choices"][0]["message"]["tool_calls"][0]
    assert call["function"]["name"] == "ping"


def test_match_helpers() -> None:
    script = Script.model_validate(
        {"match": {"regex": "^hi"}, "respond": {"text": "yo {{last_user}}"}}
    )
    assert matches(
        script,
        ChatTurn(last_user="hi there", system="", last_tool_name=None, last_tool_result=None),
    )
    assert not matches(
        script, ChatTurn(last_user="no", system="", last_tool_name=None, last_tool_result=None)
    )


async def test_openai_client_streams() -> None:
    app = create_application()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://fake-llm") as http_client:
        openai = AsyncOpenAI(base_url="http://fake-llm/v1", api_key="test", http_client=http_client)
        stream = await openai.chat.completions.create(
            model="fake-small",
            messages=[{"role": "user", "content": "stream please"}],
            stream=True,
        )
        chunks = [chunk async for chunk in stream]
    text = "".join(chunk.choices[0].delta.content or "" for chunk in chunks)
    assert text == "fake: stream please"


def test_scripted_error(client: TestClient) -> None:
    client.post(
        "/_scripts",
        json=[{"match": {"contains": "fail"}, "respond": {"error": {"status": 503}}}],
    )
    response = client.post(
        "/v1/chat/completions",
        json={"model": "fake-small", "messages": [{"role": "user", "content": "fail now"}]},
    )
    assert response.status_code == 503

"""The script set can come from the URL path. Task: M38a-T01."""

import httpx
import pytest
from fastapi.testclient import TestClient

from ar_fake_llm.app import ChatMessage, create_application, turn_from
from ar_fake_llm.background import BackgroundServer
from ar_fake_llm.scripts import Script

SCRIPTS = [{"match": {"contains": "ping"}, "respond": {"text": "pong from billing"}}]


@pytest.fixture
def client() -> TestClient:
    app = create_application()
    app.state.scripts.register("billing", [Script.model_validate(item) for item in SCRIPTS])
    return TestClient(app)


def _ask(client: TestClient, path: str, headers: dict[str, str] | None = None) -> str:
    response = client.post(
        path,
        json={"model": "any", "messages": [{"role": "user", "content": "ping"}]},
        headers=headers or {},
    )
    assert response.status_code == 200
    return str(response.json()["choices"][0]["message"]["content"])


def test_the_path_selects_the_script_set(client: TestClient) -> None:
    assert _ask(client, "/s/billing/v1/chat/completions") == "pong from billing"
    assert _ask(client, "/v1/chat/completions") == "fake: ping"
    assert _ask(client, "/s/unknown/v1/chat/completions") == "fake: ping"


def test_the_path_wins_over_a_header(client: TestClient) -> None:
    said = _ask(client, "/s/billing/v1/chat/completions", headers={"X-Fake-Script-Set": "default"})
    assert said == "pong from billing"


def test_other_routes_work_under_the_prefix(client: TestClient) -> None:
    assert client.get("/s/billing/v1/models").status_code == 200
    assert client.get("/s/").status_code == 404
    assert client.get("/s/billing").status_code == 404


def test_a_tool_result_is_named_from_the_call_that_asked_for_it() -> None:
    messages = [
        ChatMessage(role="user", content="what files are there"),
        ChatMessage.model_validate(
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "general__list_files"},
                    }
                ],
            }
        ),
        ChatMessage(role="tool", tool_call_id="call_1", content="notes.txt"),
    ]
    turn = turn_from(messages)
    assert turn.last_tool_name == "general__list_files"
    assert turn.last_tool_result == "notes.txt"
    named = turn_from([ChatMessage(role="tool", name="explicit", content="x")])
    assert named.last_tool_name == "explicit"


def test_the_background_server_answers_over_http() -> None:
    server = BackgroundServer(create_application())
    port = server.start()
    try:
        response = httpx.post(
            f"http://127.0.0.1:{port}/s/default/v1/chat/completions",
            json={"model": "any", "messages": [{"role": "user", "content": "hello"}]},
            timeout=5,
        )
        assert response.json()["choices"][0]["message"]["content"] == "fake: hello"
    finally:
        server.stop()

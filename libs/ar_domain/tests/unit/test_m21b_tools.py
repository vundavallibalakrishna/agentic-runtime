"""General tools: sandbox, workspace, fetch, search and HTTP."""

import asyncio
import uuid

import httpx
import pytest

from ar_domain.chat.service import ChatService
from ar_domain.demo_ids import demo_id
from ar_domain.tools.agent_loop import run_agent_loop
from ar_domain.tools.general import dispatch_general, remember_named_secret, sandbox_mode
from ar_domain.tools.logic import call_args_hash
from ar_domain.tools.pipeline import ToolPipeline
from ar_domain.tools.searching import SearchUnavailableError, provider_for


def _ids(qualified: str) -> uuid.UUID:
    store = ChatService()
    for version in store.tool_versions.values():
        if version.get("qualified_name") == qualified:
            return uuid.UUID(str(version["id"]))
    raise AssertionError(qualified)


def test_python_returns_output_and_a_file() -> None:
    store = ChatService()
    run_id = uuid.uuid4()
    result = dispatch_general(
        store,
        "code",
        {
            "_tenant_id": demo_id("tenant"),
            "_user_id": demo_id("admin"),
            "_run_id": run_id,
            "source": (
                "from pathlib import Path\n"
                "print('answer', 6 * 7)\n"
                "Path('/workspace/summary.txt').write_text('ready')\n"
            ),
        },
    )
    assert result["is_error"] is False
    assert "answer 42" in str(result["text"])
    presentation = result["structured"]["presentation"]
    assert presentation["exit_code"] == 0
    assert any(row["name"] == "summary.txt" for row in presentation["files"])
    assert sandbox_mode() in {"namespace", "process"}


def test_failed_python_is_an_error_the_agent_can_read() -> None:
    store = ChatService()
    result = dispatch_general(
        store,
        "code",
        {"_run_id": uuid.uuid4(), "source": "print(1/0)\n"},
    )
    assert result["is_error"] is True
    assert result["code"] == "command_failed"
    assert "ZeroDivisionError" in str(result["text"])


def test_shell_refuses_network_until_it_is_enabled() -> None:
    store = ChatService()
    denied = dispatch_general(
        store,
        "shell",
        {"_run_id": uuid.uuid4(), "command": "curl https://example.com"},
    )
    assert denied["code"] == "network_disabled"


def test_workspace_round_trip_and_path_escape() -> None:
    store = ChatService()
    run_id = uuid.uuid4()
    context = {"_tenant_id": demo_id("tenant"), "_user_id": demo_id("admin"), "_run_id": run_id}
    written = dispatch_general(
        store, "write_file", {**context, "path": "/workspace/note.txt", "content": "hello"}
    )
    assert written["is_error"] is False
    listed = dispatch_general(store, "list_files", context)
    assert "note.txt" in str(listed["text"])
    read = dispatch_general(store, "read_file", {**context, "path": "/workspace/note.txt"})
    assert read["text"] == "hello"
    escaped = dispatch_general(store, "read_file", {**context, "path": "/etc/passwd"})
    assert escaped["is_error"] is True
    huge = dispatch_general(
        store, "write_file", {**context, "path": "/workspace/big.txt", "content": "x" * 2_000_000}
    )
    assert huge["code"] == "file_too_large"


def test_uploaded_attachment_appears_in_the_workspace() -> None:
    store = ChatService()
    file_id = uuid.uuid4()
    store.files[file_id] = {"name": "data.csv", "deleted_at": None}
    store.blobs[file_id] = b"month,revenue\nJan,1\n"
    listed = dispatch_general(
        store,
        "list_files",
        {"_run_id": uuid.uuid4(), "_attachment_ids": [file_id], "path": "/workspace/inputs"},
    )
    assert "data.csv" in str(listed["text"])


def test_fetch_strips_markup_and_marks_the_page_as_data() -> None:
    store = ChatService()
    store.tenant_settings[demo_id("tenant")] = {"egress_allowlist": ["example.com"]}

    def send(method: str, url: str, **kwargs: object) -> httpx.Response:
        del method, url, kwargs
        html = (
            "<html><head><title>Notes</title></head>"
            "<body><script>alert(1)</script><p>Body</p></body></html>"
        )
        return httpx.Response(200, text=html)

    store.http_send = send  # type: ignore[attr-defined]
    result = dispatch_general(
        store,
        "fetch",
        {"_tenant_id": demo_id("tenant"), "url": "https://example.com/notes"},
    )
    assert result["is_error"] is False
    text = str(result["text"])
    assert "untrusted page data" in text
    assert "Notes" in text
    assert "alert(1)" not in text
    denied = dispatch_general(
        store,
        "fetch",
        {"_tenant_id": demo_id("tenant"), "url": "https://evil.example/phish"},
    )
    assert denied["code"] == "egress_denied"


def test_search_is_explicit_when_unconfigured_and_pluggable() -> None:
    store = ChatService()
    missing = dispatch_general(store, "search", {"query": "open data"})
    assert missing["code"] == "search_unconfigured"
    assert "AR_SEARCH_PROVIDER" in str(missing["text"])

    class Fixed:
        def search(self, query: str, *, limit: int) -> list[dict[str, str]]:
            del limit
            return [{"title": query, "url": "https://example.com", "snippet": "a row"}]

    store.search_provider = Fixed()  # type: ignore[attr-defined]
    found = provider_for(store, demo_id("tenant"))
    assert found.search("gdp", limit=1)[0]["title"] == "gdp"
    result = dispatch_general(store, "search", {"query": "gdp"})
    assert "gdp" in str(result["text"])
    assert "untrusted data" in str(result["text"])
    with pytest.raises(SearchUnavailableError, match="invented"):
        provider_for(ChatService(), None)


def test_get_runs_and_other_methods_wait_and_secrets_stay_hidden() -> None:
    store = ChatService()
    tenant = demo_id("tenant")
    secret = "super-secret-value"  # noqa: S105
    remember_named_secret(store, tenant, "vendor", secret)

    def send(method: str, url: str, **kwargs: object) -> httpx.Response:
        headers = kwargs.get("headers")
        auth = ""
        if isinstance(headers, dict):
            auth = str(headers.get("Authorization") or "")
        return httpx.Response(200, text=f"{method} {url} {auth}")

    store.http_send = send  # type: ignore[attr-defined]
    version_id = _ids("general.http")
    arguments = {
        "method": "GET",
        "url": "https://example.com/data.csv",
        "auth": {"type": "bearer", "secretName": "vendor"},
    }
    result = ToolPipeline(store).execute(
        {
            "synthetic": True,
            "tenant_id": tenant,
            "user_id": demo_id("admin"),
            "tool_version_id": version_id,
            "arguments": arguments,
            "args_hash": call_args_hash(str(version_id), arguments),
        }
    )
    assert result["status"] == "succeeded"
    long_body = "a,b\n" + "1,2\n" * 400

    def send_long(method: str, url: str, **kwargs: object) -> httpx.Response:
        del method, url, kwargs
        return httpx.Response(200, text=long_body)

    store.http_send = send_long  # type: ignore[attr-defined]
    spilled_args = {"method": "GET", "url": "https://example.com/iris.csv"}
    spilled = ToolPipeline(store).execute(
        {
            "synthetic": True,
            "tenant_id": tenant,
            "user_id": demo_id("admin"),
            "_run_id": uuid.uuid4(),
            "tool_version_id": version_id,
            "arguments": spilled_args,
            "args_hash": call_args_hash(str(version_id), spilled_args),
            "model_call_id": "get-file",
        }
    )
    assert spilled["status"] == "succeeded"
    assert "downloads/iris.csv" in str(spilled["result_preview"])
    preview = str(result["result_preview"])
    assert secret not in preview
    assert "[redacted]" in preview
    stored = next(iter(store.tool_calls.values()))
    assert secret not in str(stored["arguments_redacted"])
    post_args = {"method": "POST", "url": "https://example.com/hooks", "json": {"ok": True}}
    held = ToolPipeline(store).execute(
        {
            "synthetic": True,
            "tenant_id": tenant,
            "user_id": demo_id("admin"),
            "run_id": uuid.uuid4(),
            "tool_version_id": version_id,
            "arguments": post_args,
            "args_hash": call_args_hash(str(version_id), post_args),
            "model_call_id": "post-1",
        }
    )
    assert held["status"] == "awaiting_approval"


def test_the_loop_retries_a_failed_script() -> None:
    store = ChatService()
    store._completion_call = lambda _tenant, alias="reasoning": (  # type: ignore[method-assign]
        "Qwen/Qwen3-32B",
        {},
        5.0,
        True,
    )
    steps = [
        {
            "text": "",
            "tool_calls": [
                {"id": "c1", "name": "general__code", "arguments": {"source": "print(1/0)\n"}}
            ],
            "usage": {"tokens_in": 1, "tokens_out": 1},
        },
        {
            "text": "",
            "tool_calls": [
                {
                    "id": "c2",
                    "name": "general__code",
                    "arguments": {"source": "print('fixed', 2)\n"},
                }
            ],
            "usage": {"tokens_in": 1, "tokens_out": 1},
        },
        {"text": "Fixed the script.", "tool_calls": [], "usage": {"tokens_in": 1, "tokens_out": 1}},
    ]

    async def complete(
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
        *,
        tenant_id: uuid.UUID,
        model_alias: str,
    ) -> dict[str, object]:
        del messages, tools, tenant_id, model_alias
        return steps.pop(0)

    store.complete_turn = complete  # type: ignore[method-assign]
    tenant = demo_id("tenant")
    user = demo_id("admin")
    store.ensure_assistant(tenant, user)
    conversation = store.create_conversation(tenant, user, None, model_alias="reasoning")
    posted = store.post_message(
        tenant, user, uuid.UUID(str(conversation["id"])), "fix it", schedule=False
    )
    run = store.runs[uuid.UUID(str(posted["run"]["id"]))]
    assistant = store.messages[uuid.UUID(str(run["assistant_message_id"]))]
    assert asyncio.run(run_agent_loop(store, run, assistant, "fix it")) is True
    assert "Fixed the script." in str(assistant["text"])
    kinds = [str(event["type"]) for event in store.events[run["id"]]]
    assert "tool_call.failed" in kinds
    assert "tool_call.completed" in kinds

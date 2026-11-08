"""The sandbox agent runs commands and file operations in its workspace. Task: M40-T01."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from ar_sandbox_agent.main import create_application


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    monkeypatch.setenv("AR_SANDBOX_ROOT", str(tmp_path))
    monkeypatch.delenv("AR_SANDBOX_TOKEN", raising=False)
    return TestClient(create_application())


def _exec(client: TestClient, **arguments: Any) -> dict[str, Any]:
    return client.post("/mcp", json={"name": "sandbox.exec", "arguments": arguments}).json()


def test_exec_runs_a_command_and_reports_streams(client: TestClient) -> None:
    body = _exec(client, command="echo out; echo err 1>&2; exit 3")
    structured = body["structured"]
    assert structured["exit_code"] == 3
    assert "out" in structured["stdout"]
    assert "err" in structured["stderr"]
    assert body["is_error"] is True
    assert body["_meta"]["io.agentic-runtime/usage"]["cpu_seconds_total"] >= 0.0


def test_exec_reports_the_files_it_wrote(client: TestClient) -> None:
    body = _exec(client, command="echo answer > result.txt")
    assert body["structured"]["exit_code"] == 0
    assert any("result.txt" in name for name in body["structured"]["new_files"])
    read = client.post(
        "/mcp", json={"name": "sandbox.read_file", "arguments": {"path": "/workspace/result.txt"}}
    ).json()
    assert "answer" in read["text"]


def test_exec_times_out_and_kills_the_command(client: TestClient) -> None:
    body = _exec(client, command="sleep 5", timeout_s=1)
    assert body["structured"]["exit_code"] == 124
    assert body["is_error"] is True


def test_read_file_takes_a_byte_range(client: TestClient) -> None:
    client.put("/files/content?path=/workspace/data.txt", content=b"0123456789")
    body = client.post(
        "/mcp",
        json={
            "name": "sandbox.read_file",
            "arguments": {"path": "/workspace/data.txt", "offset": 2, "limit": 3},
        },
    ).json()
    assert body["structured"]["content"] == "234"
    assert body["structured"]["size_bytes"] == 10
    assert body["structured"]["eof"] is False


def test_write_file_handles_base64_and_append(client: TestClient) -> None:
    payload = base64.b64encode(b"hello ").decode("ascii")
    first = client.post(
        "/mcp",
        json={
            "name": "sandbox.write_file",
            "arguments": {"path": "/workspace/w.txt", "content": payload, "encoding": "base64"},
        },
    ).json()
    assert first["structured"]["bytes_written"] == 6
    client.post(
        "/mcp",
        json={
            "name": "sandbox.write_file",
            "arguments": {"path": "/workspace/w.txt", "content": "world", "append": True},
        },
    )
    read = client.post(
        "/mcp", json={"name": "sandbox.read_file", "arguments": {"path": "/workspace/w.txt"}}
    ).json()
    assert read["text"] == "hello world"


def test_list_files_can_recurse(client: TestClient) -> None:
    _exec(client, command="mkdir -p sub && echo a > sub/a.txt && echo b > b.txt")
    body = client.post(
        "/mcp",
        json={"name": "sandbox.list_files", "arguments": {"path": "/workspace", "recursive": True}},
    ).json()
    entries = body["structured"]["entries"]
    assert any("b.txt" in e for e in entries)
    assert any("sub/a.txt" in e for e in entries)


def test_exec_stays_inside_the_workspace(client: TestClient) -> None:
    body = _exec(client, command="echo hi", cwd="/etc")
    # The cwd is confined; /etc is outside the sandbox root, so it is rejected.
    assert body["is_error"] is True
    assert body.get("code") == "validation_failed"

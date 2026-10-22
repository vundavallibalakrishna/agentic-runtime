"""Sandbox agent confines paths and requires a token when one is configured."""

import os
from pathlib import Path

from fastapi.testclient import TestClient

from ar_sandbox_agent.main import create_application


def test_write_is_confined(monkeypatch: object, tmp_path: Path) -> None:
    monkeypatch.setenv("AR_SANDBOX_ROOT", str(tmp_path))  # type: ignore[attr-defined]
    monkeypatch.delenv("AR_SANDBOX_TOKEN", raising=False)  # type: ignore[attr-defined]
    client = TestClient(create_application())
    written = client.put("/files/content?path=/workspace/note.txt", content=b"hello")
    assert written.status_code == 200
    listed = client.get("/files?path=/workspace")
    assert "note.txt" in listed.text
    escaped = client.post("/mcp", json={"name": "read_file", "arguments": {"path": "/etc/passwd"}})
    assert escaped.status_code == 200
    body = escaped.json()
    assert body.get("isError") is True or body.get("is_error") is True
    os.environ.pop("AR_SANDBOX_ROOT", None)


def test_token_claim_and_exec(monkeypatch: object, tmp_path: Path) -> None:
    monkeypatch.setenv("AR_SANDBOX_ROOT", str(tmp_path))  # type: ignore[attr-defined]
    monkeypatch.setenv("AR_SANDBOX_TOKEN", "secret")  # type: ignore[attr-defined]
    client = TestClient(create_application())
    assert client.post("/admin/claim").status_code == 401
    headers = {"Authorization": "Bearer secret"}
    assert client.post("/admin/claim", headers=headers).status_code == 200
    assert client.post("/admin/snapshot", headers=headers).json()["bytes"] == 0
    assert client.post("/admin/restore", headers=headers).json()["status"] == "ready"
    ran = client.post("/mcp", headers=headers, json={"name": "exec", "arguments": {}})
    assert ran.json().get("is_error") is False
    missing = client.post(
        "/mcp",
        headers=headers,
        json={"name": "read_file", "arguments": {"path": "/workspace/missing.txt"}},
    )
    assert missing.json().get("is_error") is True
    unknown = client.post("/mcp", headers=headers, json={"name": "nope", "arguments": {}})
    assert unknown.json().get("code") == "unknown_tool"
    client.put(
        "/files/content?path=/workspace/note.txt",
        headers=headers,
        content=b"hello",
    )
    read = client.post(
        "/mcp",
        headers=headers,
        json={"name": "read_file", "arguments": {"path": "/workspace/note.txt"}},
    )
    assert "hello" in read.json()["text"]

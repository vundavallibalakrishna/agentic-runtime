"""Settings versions and the read-only tool.

Label: unit
"""

from ar_domain.chat.service import demo_id
from ar_domain.config_docs.book import SettingsBook
from ar_domain.tools.settings_tool import dispatch_settings
from ar_testing.demo import demo_store

_SCHEMA = {
    "type": "object",
    "properties": {"limit": {"type": "integer"}},
    "additionalProperties": False,
}
_WIDER = {
    "type": "object",
    "properties": {"limit": {"type": "integer"}, "note": {"type": "string"}},
    "additionalProperties": False,
}


def test_a_reinstall_keeps_the_tenant_edit_and_merges_a_new_default() -> None:
    from ar_domain.agents.access import Actor
    from ar_domain.agents.packs import _seed_settings

    store = demo_store()
    tenant = demo_id("tenant")
    actor = Actor(tenant, demo_id("admin"), frozenset())
    schema = {
        "type": "object",
        "properties": {"limit": {"type": "integer"}, "approvalGroup": {"type": "string"}},
        "additionalProperties": False,
    }
    wider = {
        "type": "object",
        "properties": {
            "limit": {"type": "integer"},
            "approvalGroup": {"type": "string"},
            "note": {"type": "string"},
        },
        "additionalProperties": False,
    }
    manifest = {
        "spec": {
            "resources": [
                {
                    "kind": "Agent",
                    "metadata": {"slug": "scan"},
                    "spec": {
                        "settingsSchema": schema,
                        "settings": {"limit": 1, "approvalGroup": "reviewers"},
                    },
                }
            ]
        }
    }
    _seed_settings(store, actor, manifest)
    SettingsBook(store).save(
        tenant,
        demo_id("admin"),
        "agent",
        "scan",
        schema,
        {"limit": 9, "approvalGroup": "reviewers"},
    )
    manifest["spec"]["resources"][0]["spec"]["settingsSchema"] = wider
    manifest["spec"]["resources"][0]["spec"]["settings"] = {
        "limit": 1,
        "approvalGroup": "reviewers",
        "note": "fresh",
    }
    _seed_settings(store, actor, manifest)
    latest = SettingsBook(store).latest(tenant, "agent", "scan")
    assert latest["version"] == 3
    assert latest["document"] == {"limit": 9, "approvalGroup": "reviewers", "note": "fresh"}
    again = SettingsBook(store).latest(tenant, "agent", "scan")
    _seed_settings(store, actor, manifest)
    assert SettingsBook(store).latest(tenant, "agent", "scan")["version"] == again["version"]


def test_an_explicit_schema_change_is_a_new_audited_version() -> None:
    store = demo_store()
    tenant = demo_id("tenant")
    book = SettingsBook(store)
    first = book.save(tenant, demo_id("admin"), "agent", "scan", _SCHEMA, {"limit": 1})
    assert first["version"] == 1
    second = book.save(tenant, demo_id("admin"), "agent", "scan", _WIDER, {"limit": 1, "note": "a"})
    assert second["version"] == 2
    schema = second["schema"]
    assert isinstance(schema, dict)
    assert schema["properties"]["note"]["type"] == "string"
    assert store.audit_log[-1]["detail"]["schema_changed"] is True
    agent_id = demo_id("builder")
    store.agents[agent_id] = {"id": agent_id, "tenant_id": tenant, "slug": "scan"}
    loaded = dispatch_settings(
        store,
        "read",
        {
            "_tenant_id": tenant,
            "_agent_id": agent_id,
            "resourceType": "agent",
            "resourceId": "scan",
        },
    )
    assert loaded["is_error"] is False
    assert loaded["structured"]["document"] == {"limit": 1, "note": "a"}
    other = dispatch_settings(
        store,
        "read",
        {
            "_tenant_id": tenant,
            "_agent_id": agent_id,
            "resourceType": "agent",
            "resourceId": "someone-else",
        },
    )
    assert other["is_error"] is True

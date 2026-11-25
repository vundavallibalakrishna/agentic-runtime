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
    loaded = dispatch_settings(
        store,
        "read",
        {"_tenant_id": tenant, "resourceType": "agent", "resourceId": "scan"},
    )
    assert loaded["is_error"] is False
    assert loaded["structured"]["document"] == {"limit": 1, "note": "a"}

"""Tool arguments stay byte-exact when a response is camelCased.

Label: unit
"""

from ar_common.json_api import camelize


def test_an_edited_argument_keeps_its_spelling() -> None:
    body = {
        "qualified_name": "pack.example",
        "arguments": {"target_date": "2026-01-02"},
        "schema": {"properties": {"target_date": {"type": "string"}}},
        "preview": {"summary": "one"},
        "fields": [{"quote_verified": True}],
        "result": {"target_date": "2026-01-02"},
        "document": {"register_write_tool": "rest.post"},
    }
    public = camelize(body)
    assert isinstance(public, dict)
    assert public["qualifiedName"] == "pack.example"
    assert public["arguments"] == {"target_date": "2026-01-02"}
    assert public["schema"]["properties"]["target_date"]["type"] == "string"
    assert public["fields"] == [{"quote_verified": True}]
    assert public["result"] == {"target_date": "2026-01-02"}
    assert public["document"] == {"register_write_tool": "rest.post"}


def test_a_json_rpc_result_is_still_camel_case() -> None:
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "structured_content": {"status": "approval_required", "approval_id": "a"},
            "push_notification_config": {"url": "https://example.com/push"},
            "arguments": {"target_date": "2026-01-02"},
        },
    }
    public = camelize(body)
    assert isinstance(public, dict)
    result = public["result"]
    assert isinstance(result, dict)
    assert result["structuredContent"]["approvalId"] == "a"
    assert result["pushNotificationConfig"]["url"] == "https://example.com/push"
    assert result["arguments"] == {"target_date": "2026-01-02"}

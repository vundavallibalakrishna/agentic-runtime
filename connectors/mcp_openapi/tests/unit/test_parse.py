"""OpenAPI import and a stub upstream call."""

import httpx

from ar_mcp_openapi.parse import merge_schema, operations_from, risk_for
from ar_mcp_openapi.server import handle

PET = {
    "openapi": "3.1.0",
    "paths": {
        "/pets": {
            "get": {"operationId": "listPets", "summary": "List"},
            "post": {
                "operationId": "createPet",
                "requestBody": {
                    "required": True,
                    "content": {"application/json": {"schema": {"type": "object"}}},
                },
            },
        }
    },
}


def test_methods_map_to_the_spec_risk_classes() -> None:
    tools = {item["name"]: item for item in operations_from(PET)}
    assert tools["list_pets"]["risk_class"] == risk_for("get") == "R0"
    assert tools["create_pet"]["risk_class"] == "W2"
    merged = merge_schema(
        tools["list_pets"]["input_schema"],
        {"properties": {"limit": {"type": "integer"}}, "required": ["limit"]},
    )
    assert "limit" in merged["properties"]
    assert "limit" in merged["required"]


def test_call_reaches_the_stub_api() -> None:
    def send(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/pets"
        return httpx.Response(200, text="doggie")

    body = handle(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "list_pets", "arguments": {}},
        },
        document=PET,
        base_url="https://pets.example/",
        transport=httpx.MockTransport(send),
        resolver=lambda _host: ["1.1.1.1"],
    )
    assert body["result"]["content"][0]["text"] == "doggie"
    assert body["result"]["isError"] is False

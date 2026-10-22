"""OpenAPI 3.0/3.1 import. Spec: docs/03-specs/08-tool-registry-mcp.md §11.

HTTP method risk follows spec 08 §7: GET/HEAD R0, POST/PUT/PATCH W2, DELETE W3.
"""

import re
from typing import cast

import orjson

_NAME = re.compile(r"^[a-z][a-z0-9_]{0,47}$")


class OpenApiError(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


def load_document(raw: bytes | str | dict[str, object]) -> dict[str, object]:
    if isinstance(raw, dict):
        return raw
    text = raw.decode() if isinstance(raw, bytes) else raw
    try:
        loaded = orjson.loads(text)
    except orjson.JSONDecodeError as exc:
        raise OpenApiError("the OpenAPI document is not JSON") from exc
    if not isinstance(loaded, dict):
        raise OpenApiError("the OpenAPI document must be an object")
    return cast("dict[str, object]", loaded)


def risk_for(method: str) -> str:
    verb = method.upper()
    if verb in {"GET", "HEAD"}:
        return "R0"
    if verb == "DELETE":
        return "W3"
    if verb in {"POST", "PUT", "PATCH"}:
        return "W2"
    return "R1"


def operations_from(
    document: dict[str, object], selected: list[str] | None = None
) -> list[dict[str, object]]:
    paths = document.get("paths")
    if not isinstance(paths, dict) or not paths:
        raise OpenApiError("the document has no paths")
    chosen = set(selected or [])
    found: list[dict[str, object]] = []
    for path, item in paths.items():
        if not isinstance(item, dict):
            continue
        for method, operation in item.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete", "head"}:
                continue
            if not isinstance(operation, dict):
                continue
            operation_id = str(operation.get("operationId") or "")
            if not operation_id:
                raise OpenApiError(f"{method.upper()} {path} has no operationId")
            if chosen and operation_id not in chosen:
                continue
            name = _tool_name(operation_id)
            schema = _input_schema(operation, document)
            summary = str(operation.get("summary") or "")
            description = str(operation.get("description") or "")
            text = " ".join(part for part in (summary, description) if part).strip() or name
            risk = risk_for(method)
            found.append(
                {
                    "name": name,
                    "operation_id": operation_id,
                    "method": method.upper(),
                    "path": str(path),
                    "title": summary or name,
                    "description": text[:4000],
                    "input_schema": schema,
                    "risk_class": risk,
                    "annotations": {"openWorldHint": True, "readOnlyHint": risk == "R0"},
                }
            )
    if chosen and len(found) != len(chosen):
        raise OpenApiError("one or more operations were not in the document")
    if not found:
        raise OpenApiError("no operations were selected")
    return found


def merge_schema(base: dict[str, object], extra: dict[str, object]) -> dict[str, object]:
    """Overlay caller properties onto the generated input schema."""
    properties = _object(base.get("properties"))
    incoming = _object(extra.get("properties"))
    properties.update(incoming)
    required = [str(item) for item in _items(base.get("required"))]
    for name in _items(extra.get("required")):
        text = str(name)
        if text not in required:
            required.append(text)
    merged: dict[str, object] = {
        "type": "object",
        "properties": properties,
        "additionalProperties": False,
    }
    if required:
        merged["required"] = required
    return merged


def _object(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return {str(key): item for key, item in value.items()}
    return {}


def _items(value: object) -> list[object]:
    if isinstance(value, list):
        return list(value)
    return []


def _tool_name(operation_id: str) -> str:
    split = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", operation_id)
    cleaned = "".join(char.lower() if char.isalnum() else "_" for char in split)
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    cleaned = cleaned.strip("_")
    if _NAME.match(cleaned) is None:
        raise OpenApiError(f"operationId {operation_id} is not a tool name")
    return cleaned


def _input_schema(operation: dict[str, object], document: dict[str, object]) -> dict[str, object]:
    properties: dict[str, object] = {}
    required: list[str] = []
    parameters = operation.get("parameters")
    if isinstance(parameters, list):
        for param in parameters:
            if not isinstance(param, dict) or param.get("in") not in {"path", "query", "header"}:
                continue
            if str(param.get("name", "")).lower() == "authorization":
                continue
            name = str(param.get("name"))
            schema = _resolve(param.get("schema"), document)
            properties[name] = schema if isinstance(schema, dict) else {"type": "string"}
            if param.get("required") is True:
                required.append(name)
    body = operation.get("requestBody")
    if isinstance(body, dict):
        content = body.get("content")
        json_body = content.get("application/json") if isinstance(content, dict) else None
        if isinstance(json_body, dict):
            schema = _resolve(json_body.get("schema"), document)
            if isinstance(schema, dict):
                properties["body"] = schema
                if body.get("required") is True:
                    required.append("body")
    result: dict[str, object] = {
        "type": "object",
        "properties": properties,
        "additionalProperties": False,
    }
    if required:
        result["required"] = required
    return result


def _resolve(schema: object, document: dict[str, object]) -> object:
    if not isinstance(schema, dict):
        return {"type": "string"}
    ref = schema.get("$ref")
    if isinstance(ref, str) and ref.startswith("#/"):
        node: object = document
        for part in ref.removeprefix("#/").split("/"):
            if not isinstance(node, dict) or part not in node:
                return {"type": "object"}
            node = node[part]
        return node
    return schema

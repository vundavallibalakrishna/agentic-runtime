"""Validate a final answer against the agent output schema and describe one retry."""

from __future__ import annotations

import orjson
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError


def schema_for(
    definition: dict[str, object], override: object | None = None
) -> dict[str, object] | None:
    """The turn schema: a caller ``responseFormat``, otherwise the agent output schema."""
    if isinstance(override, dict) and override:
        return override
    return output_schema(definition)


def output_schema(definition: dict[str, object]) -> dict[str, object] | None:
    """The schema from ``output.jsonSchema``, ``json_schema`` or ``schema``."""
    output = definition.get("output")
    if not isinstance(output, dict):
        return None
    for key in ("json_schema", "jsonSchema", "schema"):
        value = output.get(key)
        if isinstance(value, dict) and value:
            return value
    return None


def check_response_format(schema: object) -> dict[str, object] | None:
    """Reject a caller schema that is not a JSON Schema document. None means no override."""
    if schema is None:
        return None
    if not isinstance(schema, dict) or not schema:
        from ar_common.errors import ArError, ErrorCode  # noqa: PLC0415

        raise ArError(ErrorCode.VALIDATION_FAILED, "responseFormat must be a JSON Schema object")
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        from ar_common.errors import ArError, ErrorCode  # noqa: PLC0415

        raise ArError(
            ErrorCode.VALIDATION_FAILED, f"responseFormat is not a JSON Schema ({exc.message})"
        ) from exc
    return schema


def validate_output(text: str, schema: dict[str, object]) -> str | None:
    """Return an error string when ``text`` is not JSON matching ``schema``."""
    raw = _strip_fence(text)
    try:
        parsed = orjson.loads(raw)
    except orjson.JSONDecodeError as exc:
        return f"invalid JSON ({exc.msg})"
    if not isinstance(parsed, dict):
        return "the answer must be a JSON object"
    try:
        validator = Draft202012Validator(schema)
    except SchemaError as exc:
        return f"output schema is invalid ({exc.message})"
    errors = sorted(validator.iter_errors(parsed), key=lambda item: str(item.path))
    if not errors:
        return None
    first = errors[0]
    path = ".".join(str(part) for part in first.path) or "$"
    return f"{path}: {first.message}"


def _strip_fence(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()

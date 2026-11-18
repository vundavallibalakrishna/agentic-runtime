"""CamelCase conversion for JSON that leaves the process.

Python and the database stay snake_case. Keys in REST bodies, problem
documents, pagination envelopes, SSE payloads and webhooks are camelCase.
Public models live in ``ar_contracts.api_model.ApiModel``. :func:`camelize` rewrites
free-form objects that are not Pydantic fields, such as pagination items.
:func:`dumps` is the encoder for that JSON. It accepts the types a database
driver returns, including asyncpg's UUID subclass, datetimes and Decimals.
"""

import uuid
from datetime import date, datetime, time
from decimal import Decimal

import orjson
from pydantic.alias_generators import to_camel

# Free-form objects whose keys are data, not API fields, so they are copied through
# unchanged. Provider protocol objects (``request_options``, ``default_params``) are sent
# upstream as stored, so a round trip must not rename ``chat_template_kwargs``. A tool's
# ``input_schema``/``output_schema`` is a JSON Schema whose ``properties`` keys are the
# tool's parameter names (``file_id``); camelCasing them would show names the tool rejects.
OPAQUE_JSON_KEYS = frozenset(
    {
        "request_options",
        "requestOptions",
        "default_params",
        "defaultParams",
        "input_schema",
        "inputSchema",
        "output_schema",
        "outputSchema",
    }
)


def camel_key(name: str) -> str:
    """Return the camelCase form of a JSON object key.

    Keys that already contain no underscore are left unchanged, so a second
    pass is safe and tokens such as ``requestId`` stay put.
    """
    if "_" not in name:
        return name
    return to_camel(name)


def _json_default(value: object) -> str:
    """Text for a driver type orjson does not encode itself.

    orjson accepts ``uuid.UUID`` and ``datetime`` only as the exact builtin
    type. asyncpg's UUID is a subclass, so it has to be handled here. A Decimal
    is written as its full decimal text, not a binary float.
    """
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, time):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value, "f")
    raise TypeError(f"{type(value).__name__} is not JSON")


def dumps(value: object) -> bytes:
    """JSON bytes for a response. Driver UUIDs, datetimes and Decimals are safe."""
    return orjson.dumps(value, default=_json_default)


def camelize(value: object) -> object:
    """Recursively rewrite object keys. Values, including error codes, stay as they are.

    Values under :data:`OPAQUE_JSON_KEYS` are copied through unchanged.
    """
    if isinstance(value, dict):
        rewritten: dict[str, object] = {}
        for key, item in value.items():
            name = str(key)
            public = camel_key(name)
            if name in OPAQUE_JSON_KEYS or public in OPAQUE_JSON_KEYS:
                rewritten[public] = item
            else:
                rewritten[public] = camelize(item)
        return rewritten
    if isinstance(value, list):
        return [camelize(item) for item in value]
    return value

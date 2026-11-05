"""CamelCase conversion for JSON that leaves the process.

Python and the database stay snake_case. Keys in REST bodies, problem
documents, pagination envelopes, SSE payloads and webhooks are camelCase.
Public models live in ``ar_contracts.api_model.ApiModel``. :func:`camelize` rewrites
free-form objects that are not Pydantic fields, such as pagination items.
"""

from pydantic.alias_generators import to_camel

# Provider protocol objects. Their keys are sent upstream as stored, so a
# read/write round trip must not rename ``chat_template_kwargs``.
OPAQUE_JSON_KEYS = frozenset({"request_options", "requestOptions"})


def camel_key(name: str) -> str:
    """Return the camelCase form of a JSON object key.

    Keys that already contain no underscore are left unchanged, so a second
    pass is safe and tokens such as ``requestId`` stay put.
    """
    if "_" not in name:
        return name
    return to_camel(name)


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

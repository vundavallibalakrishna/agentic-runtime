"""Fail when a public JSON Schema property is not camelCase.

Public models are ``ar_contracts.api_model.ApiModel`` subclasses. JSON Schema is
generated with aliases, which is the contract the web app and generated clients see.
Env vars, database columns and Python attributes are not checked.
"""

from __future__ import annotations

import re
import sys

from pydantic import BaseModel

from ar_contracts.api_model import ApiModel
from ar_contracts.definitions import SCHEMA_MODELS
from ar_contracts.stream import RunEvent

CAMEL = re.compile(r"^[a-z][a-zA-Z0-9]*$")

# Importing RunEvent loads the stream models so ApiModel.__subclasses__ sees them.
_ = RunEvent


def _models() -> list[type[BaseModel]]:
    found: list[type[BaseModel]] = [
        model
        for model in SCHEMA_MODELS.values()
        if isinstance(model, type) and issubclass(model, BaseModel)
    ]
    seen: set[type[BaseModel]] = set()

    def walk(cls: type[BaseModel]) -> None:
        if cls in seen:
            return
        seen.add(cls)
        for sub in cls.__subclasses__():
            walk(sub)

    walk(ApiModel)
    found.extend(cls for cls in seen if cls is not ApiModel and cls not in found)
    return found


def _check_props(props: object, path: str, errors: list[str]) -> None:
    if not isinstance(props, dict):
        return
    for key, child in props.items():
        if isinstance(key, str) and not CAMEL.fullmatch(key):
            errors.append(f"{path}.{key}")
        _check(child, f"{path}.{key}", errors)


def _check_named(node: dict[object, object], path: str, errors: list[str]) -> None:
    for key in ("$defs", "definitions"):
        defs = node.get(key)
        if isinstance(defs, dict):
            for name, child in defs.items():
                _check(child, f"{path}.{key}.{name}", errors)
    for key in ("items", "additionalProperties", "not"):
        if key in node:
            _check(node[key], f"{path}.{key}", errors)


def _check_lists(node: dict[object, object], path: str, errors: list[str]) -> None:
    for key in ("anyOf", "oneOf", "allOf", "prefixItems"):
        value = node.get(key)
        if isinstance(value, list):
            for index, child in enumerate(value):
                _check(child, f"{path}.{key}[{index}]", errors)


def _check(node: object, path: str, errors: list[str]) -> None:
    if isinstance(node, dict):
        _check_props(node.get("properties"), path, errors)
        _check_named(node, path, errors)
        _check_lists(node, path, errors)
    elif isinstance(node, list):
        for index, child in enumerate(node):
            _check(child, f"{path}[{index}]", errors)


def main() -> None:
    errors: list[str] = []
    models = _models()
    for model in models:
        schema = model.model_json_schema(by_alias=True)
        _check(schema, model.__name__, errors)
    if errors:
        print("public schema fields are not camelCase:", file=sys.stderr)
        print("\n".join(errors), file=sys.stderr)
        raise SystemExit(1)
    print(f"public schema fields are camelCase ({len(models)} models)")


if __name__ == "__main__":
    main()

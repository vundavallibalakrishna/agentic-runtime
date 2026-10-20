"""Fail when a public JSON schema still exposes a snake_case property.

Public models are ``ApiModel`` subclasses in ``ar_contracts`` and request bodies
in ``ar_api``. Python field names stay snake_case; the alias and JSON Schema
property must be camelCase.
"""

import sys

from pydantic_settings import BaseSettings

from ar_contracts.json_api import (
    ApiModel,
    _models_defined_in,
    contract_violations,
    iter_public_models,
)


def api_model_violations() -> list[str]:
    """Request models under ``ar_api`` must inherit the public base."""
    violations: list[str] = []
    for model in _models_defined_in("ar_api"):
        if model.__name__.startswith("_") or issubclass(model, BaseSettings):
            continue
        if not issubclass(model, ApiModel):
            violations.append(f"{model.__module__}.{model.__name__} does not inherit ApiModel")
    return violations


def main() -> None:
    violations = contract_violations() + api_model_violations()
    if violations:
        print("public JSON is not camelCase:", file=sys.stderr)
        for item in violations:
            print(f"  {item}", file=sys.stderr)
        raise SystemExit(1)
    print(f"{len(iter_public_models())} public models use camelCase JSON")


if __name__ == "__main__":
    main()

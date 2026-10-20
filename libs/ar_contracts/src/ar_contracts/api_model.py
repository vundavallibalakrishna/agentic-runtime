"""Public JSON models. Spec: docs/02-architecture/adr/ADR-0026-public-json-camel-case.md."""

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class ApiModel(BaseModel):
    """Python attributes stay snake_case. Public JSON uses camelCase aliases.

    `populate_by_name` accepts either form on input. Serialisation and JSON Schema
    use the alias, so generated TypeScript and Zod types are camelCase.
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        serialize_by_alias=True,
        extra="forbid",
    )

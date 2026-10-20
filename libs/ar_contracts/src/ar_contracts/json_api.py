"""Public JSON models. Spec examples that show snake_case keys are camelCase on the wire.

Python attributes stay snake_case. ``alias_generator`` plus ``populate_by_name``
accept either spelling on input. ``public_dump`` and JSON Schema use the aliases.
``model_dump()`` without ``by_alias`` stays snake_case for rows and settings JSON.
"""

from typing import cast

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from ar_common.json_api import camel_key, camelize

_PUBLIC = ConfigDict(
    alias_generator=to_camel,
    populate_by_name=True,
    extra="forbid",
)


class ApiModel(BaseModel):
    """Base for every document a UI, webhook receiver or SSE client parses."""

    model_config = _PUBLIC

    def public_dump(self) -> dict[str, object]:
        """JSON-ready object with camelCase keys, including nested free-form objects."""
        dumped = camelize(self.model_dump(mode="json", by_alias=True))
        if not isinstance(dumped, dict):
            raise TypeError("public JSON must be an object")
        return cast("dict[str, object]", dumped)


class FrozenApiModel(ApiModel):
    """Immutable public document (definitions and stream events)."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
        frozen=True,
    )


class ProblemField(ApiModel):
    """One entry in a problem ``errors`` array."""

    loc: list[str | int]
    msg: str
    type: str


class ProblemDetails(ApiModel):
    """RFC 9457 body. ``code`` values stay snake_case; the key ``requestId`` does not."""

    type: str
    title: str
    status: int
    code: str
    detail: str
    instance: str
    request_id: str
    errors: list[ProblemField] = Field(default_factory=list)


class Page(ApiModel):
    """Cursor page. Conventions §4, with camelCase keys.

    Items are JSON objects. A recursive ``JsonValue`` schema is too deep for the
    generated Zod client, and list endpoints return objects.
    """

    items: list[dict[str, object]] = Field(default_factory=list)
    next_cursor: str | None = None
    has_more: bool = False


def page_body(
    items: list[dict[str, object]],
    *,
    next_cursor: str | None = None,
) -> dict[str, object]:
    """Serialize a list endpoint envelope."""
    encoded: list[dict[str, object]] = []
    for item in items:
        dumped = camelize(item)
        if isinstance(dumped, dict):
            encoded.append(cast("dict[str, object]", dumped))
    return Page(
        items=encoded,
        next_cursor=next_cursor,
        has_more=next_cursor is not None,
    ).public_dump()


def public_property_violations(model: type[ApiModel]) -> list[str]:
    """Return schema property names that are not camelCase aliases of their fields."""
    violations: list[str] = []
    for name, field in model.model_fields.items():
        alias = field.alias or name
        expected = camel_key(name)
        if alias != expected or "_" in alias:
            violations.append(f"{model.__name__}.{name} -> {alias}")
    schema = model.model_json_schema(by_alias=True)
    violations.extend(
        f"{model.__name__} schema property {prop}" for prop in _snake_properties(schema)
    )
    return violations


def _snake_properties(node: object) -> list[str]:
    found: list[str] = []
    if isinstance(node, dict):
        properties = node.get("properties")
        if isinstance(properties, dict):
            found.extend(str(key) for key in properties if "_" in str(key))
        for value in node.values():
            found.extend(_snake_properties(value))
    elif isinstance(node, list):
        for value in node:
            found.extend(_snake_properties(value))
    return found


def contract_violations() -> list[str]:
    """Alias and schema violations for every concrete contract model."""
    violations: list[str] = []
    models = iter_public_models()
    if not models:
        return ["no public models were discovered"]
    inheriting = set(models)
    for public in models:
        violations.extend(public_property_violations(public))
    for defined in _models_defined_in("ar_contracts"):
        if defined in inheriting or defined.__name__ in {"ApiModel"}:
            continue
        if not issubclass(defined, ApiModel):
            violations.append(f"{defined.__module__}.{defined.__name__} does not inherit ApiModel")
    return violations


def _models_defined_in(package_name: str) -> list[type[BaseModel]]:
    import importlib  # noqa: PLC0415
    import pkgutil  # noqa: PLC0415

    package = importlib.import_module(package_name)
    found: list[type[BaseModel]] = []
    paths = getattr(package, "__path__", None)
    if paths is None:
        return found
    for module_info in pkgutil.walk_packages(paths, package.__name__ + "."):
        module = importlib.import_module(module_info.name)
        found.extend(
            obj
            for obj in vars(module).values()
            if isinstance(obj, type)
            and issubclass(obj, BaseModel)
            and obj.__module__ == module.__name__
        )
    return found


def iter_public_models() -> list[type[ApiModel]]:
    """Import every contract module and return concrete ``ApiModel`` subclasses."""
    import importlib  # noqa: PLC0415
    import pkgutil  # noqa: PLC0415

    import ar_contracts  # noqa: PLC0415

    for module in pkgutil.walk_packages(ar_contracts.__path__, "ar_contracts."):
        importlib.import_module(module.name)
    found: list[type[ApiModel]] = []

    def walk(cls: type[ApiModel]) -> None:
        for sub in cls.__subclasses__():
            if sub.__module__.startswith("ar_contracts."):
                found.append(sub)
            walk(sub)

    walk(ApiModel)
    return found

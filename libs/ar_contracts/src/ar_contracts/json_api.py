"""Pagination and problem documents on the public API.

The shared base is :class:`ar_contracts.api_model.ApiModel`. Python attributes stay
snake_case. ``model_dump()`` emits camelCase aliases. Pass ``by_alias=False`` when
a document is stored in a JSON column.
"""

from typing import cast

from pydantic import Field

from ar_common.json_api import camelize
from ar_contracts.api_model import ApiModel


class ProblemField(ApiModel):
    """One entry in a problem ``errors`` array."""

    loc: list[str | int]
    msg: str
    type: str


class ProblemDetails(ApiModel):
    """RFC 9457 body. ``code`` values stay snake_case; the key is ``requestId``."""

    type: str
    title: str
    status: int
    code: str
    detail: str
    instance: str
    request_id: str
    errors: list[ProblemField] = Field(default_factory=list)


class Page(ApiModel):
    """Cursor page. Items are JSON objects so the generated Zod schema stays finite."""

    items: list[dict[str, object]] = Field(default_factory=list)
    next_cursor: str | None = None
    has_more: bool = False


def public_dump(model: ApiModel) -> dict[str, object]:
    """JSON-ready object with camelCase keys, including nested free-form objects."""
    dumped = camelize(model.model_dump(mode="json"))
    if not isinstance(dumped, dict):
        raise TypeError("public JSON must be an object")
    return cast("dict[str, object]", dumped)


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
    return public_dump(
        Page(
            items=encoded,
            next_cursor=next_cursor,
            has_more=next_cursor is not None,
        )
    )

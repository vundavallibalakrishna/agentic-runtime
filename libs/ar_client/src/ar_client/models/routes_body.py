from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast

if TYPE_CHECKING:
    from ..models.route_body import RouteBody


T = TypeVar("T", bound="RoutesBody")


@_attrs_define
class RoutesBody:
    """
    Attributes:
        routes (list[RouteBody] | Unset):
    """

    routes: list[RouteBody] | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        from ..models.route_body import RouteBody  # noqa: PLC0415

        routes: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.routes, Unset):
            routes = []
            for routes_item_data in self.routes:
                routes_item = routes_item_data.to_dict()
                routes.append(routes_item)

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if routes is not UNSET:
            field_dict["routes"] = routes

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.route_body import RouteBody  # noqa: PLC0415

        d = dict(src_dict)
        _routes = d.pop("routes", UNSET)
        routes: list[RouteBody] | Unset = UNSET
        if _routes is not UNSET:
            routes = []
            for routes_item_data in _routes:
                routes_item = RouteBody.from_dict(routes_item_data)

                routes.append(routes_item)

        routes_body = cls(
            routes=routes,
        )

        return routes_body

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset


T = TypeVar("T", bound="RouteBody")


@_attrs_define
class RouteBody:
    """
    Attributes:
        id (str):
        base_url (str):
        model (str):
        secret_name (str | Unset):  Default: ''.
    """

    id: str
    base_url: str
    model: str
    secret_name: str | Unset = ""

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        base_url = self.base_url

        model = self.model

        secret_name = self.secret_name

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "id": id,
                "baseUrl": base_url,
                "model": model,
            }
        )
        if secret_name is not UNSET:
            field_dict["secretName"] = secret_name

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        id = d.pop("id")

        base_url = d.pop("baseUrl")

        model = d.pop("model")

        secret_name = d.pop("secretName", UNSET)

        route_body = cls(
            id=id,
            base_url=base_url,
            model=model,
            secret_name=secret_name,
        )

        return route_body

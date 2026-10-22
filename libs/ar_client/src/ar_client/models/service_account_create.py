from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset


T = TypeVar("T", bound="ServiceAccountCreate")


@_attrs_define
class ServiceAccountCreate:
    """
    Attributes:
        name (str):
        description (str | Unset):  Default: ''.
        allow_on_behalf_of (bool | Unset):  Default: False.
    """

    name: str
    description: str | Unset = ""
    allow_on_behalf_of: bool | Unset = False

    def to_dict(self) -> dict[str, Any]:
        name = self.name

        description = self.description

        allow_on_behalf_of = self.allow_on_behalf_of

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "name": name,
            }
        )
        if description is not UNSET:
            field_dict["description"] = description
        if allow_on_behalf_of is not UNSET:
            field_dict["allowOnBehalfOf"] = allow_on_behalf_of

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        name = d.pop("name")

        description = d.pop("description", UNSET)

        allow_on_behalf_of = d.pop("allowOnBehalfOf", UNSET)

        service_account_create = cls(
            name=name,
            description=description,
            allow_on_behalf_of=allow_on_behalf_of,
        )

        return service_account_create

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast


T = TypeVar("T", bound="RoleCreate")


@_attrs_define
class RoleCreate:
    """
    Attributes:
        key (str):
        name (str):
        permissions (list[str]):
        description (str | Unset):  Default: ''.
    """

    key: str
    name: str
    permissions: list[str]
    description: str | Unset = ""

    def to_dict(self) -> dict[str, Any]:
        key = self.key

        name = self.name

        permissions = self.permissions

        description = self.description

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "key": key,
                "name": name,
                "permissions": permissions,
            }
        )
        if description is not UNSET:
            field_dict["description"] = description

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        key = d.pop("key")

        name = d.pop("name")

        permissions = cast(list[str], d.pop("permissions"))

        description = d.pop("description", UNSET)

        role_create = cls(
            key=key,
            name=name,
            permissions=permissions,
            description=description,
        )

        return role_create

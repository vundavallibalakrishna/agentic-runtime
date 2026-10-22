from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast


T = TypeVar("T", bound="RolePatch")


@_attrs_define
class RolePatch:
    """
    Attributes:
        name (None | str | Unset):
        permissions (list[str] | None | Unset):
    """

    name: None | str | Unset = UNSET
    permissions: list[str] | None | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        name: None | str | Unset
        if isinstance(self.name, Unset):
            name = UNSET
        else:
            name = self.name

        permissions: list[str] | None | Unset
        if isinstance(self.permissions, Unset):
            permissions = UNSET
        elif isinstance(self.permissions, list):
            permissions = self.permissions

        else:
            permissions = self.permissions

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if name is not UNSET:
            field_dict["name"] = name
        if permissions is not UNSET:
            field_dict["permissions"] = permissions

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)

        def _parse_name(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        name = _parse_name(d.pop("name", UNSET))

        def _parse_permissions(data: object) -> list[str] | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                permissions_type_0 = cast(list[str], data)

                return permissions_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(list[str] | None | Unset, data)

        permissions = _parse_permissions(d.pop("permissions", UNSET))

        role_patch = cls(
            name=name,
            permissions=permissions,
        )

        return role_patch

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset


T = TypeVar("T", bound="UninstallBody")


@_attrs_define
class UninstallBody:
    """
    Attributes:
        drop_schema (bool | Unset):  Default: False.
    """

    drop_schema: bool | Unset = False

    def to_dict(self) -> dict[str, Any]:
        drop_schema = self.drop_schema

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if drop_schema is not UNSET:
            field_dict["dropSchema"] = drop_schema

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        drop_schema = d.pop("dropSchema", UNSET)

        uninstall_body = cls(
            drop_schema=drop_schema,
        )

        return uninstall_body

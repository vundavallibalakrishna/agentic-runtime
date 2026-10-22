from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset


T = TypeVar("T", bound="ExportBody")


@_attrs_define
class ExportBody:
    """
    Attributes:
        path (str | Unset):  Default: ''.
        name (str | Unset):  Default: ''.
    """

    path: str | Unset = ""
    name: str | Unset = ""

    def to_dict(self) -> dict[str, Any]:
        path = self.path

        name = self.name

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if path is not UNSET:
            field_dict["path"] = path
        if name is not UNSET:
            field_dict["name"] = name

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        path = d.pop("path", UNSET)

        name = d.pop("name", UNSET)

        export_body = cls(
            path=path,
            name=name,
        )

        return export_body

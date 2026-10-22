from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset


T = TypeVar("T", bound="RollbackBody")


@_attrs_define
class RollbackBody:
    """
    Attributes:
        version (int):
        change_note (str | Unset):  Default: ''.
    """

    version: int
    change_note: str | Unset = ""

    def to_dict(self) -> dict[str, Any]:
        version = self.version

        change_note = self.change_note

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "version": version,
            }
        )
        if change_note is not UNSET:
            field_dict["changeNote"] = change_note

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        version = d.pop("version")

        change_note = d.pop("changeNote", UNSET)

        rollback_body = cls(
            version=version,
            change_note=change_note,
        )

        return rollback_body

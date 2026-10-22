from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset


T = TypeVar("T", bound="NotesBody")


@_attrs_define
class NotesBody:
    """
    Attributes:
        notes (str | Unset):  Default: ''.
    """

    notes: str | Unset = ""

    def to_dict(self) -> dict[str, Any]:
        notes = self.notes

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if notes is not UNSET:
            field_dict["notes"] = notes

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        notes = d.pop("notes", UNSET)

        notes_body = cls(
            notes=notes,
        )

        return notes_body

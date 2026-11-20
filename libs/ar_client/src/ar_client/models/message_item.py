from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset


T = TypeVar("T", bound="MessageItem")


@_attrs_define
class MessageItem:
    """
    Attributes:
        id (str | Unset):  Default: ''.
        text (str | Unset):  Default: ''.
    """

    id: str | Unset = ""
    text: str | Unset = ""

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        text = self.text

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if id is not UNSET:
            field_dict["id"] = id
        if text is not UNSET:
            field_dict["text"] = text

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        id = d.pop("id", UNSET)

        text = d.pop("text", UNSET)

        message_item = cls(
            id=id,
            text=text,
        )

        return message_item

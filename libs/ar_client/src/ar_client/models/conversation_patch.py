from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast






T = TypeVar("T", bound="ConversationPatch")



@_attrs_define
class ConversationPatch:
    """ 
        Attributes:
            title (None | str | Unset):
            pinned (bool | None | Unset):
     """

    title: None | str | Unset = UNSET
    pinned: bool | None | Unset = UNSET





    def to_dict(self) -> dict[str, Any]:
        title: None | str | Unset
        if isinstance(self.title, Unset):
            title = UNSET
        else:
            title = self.title

        pinned: bool | None | Unset
        if isinstance(self.pinned, Unset):
            pinned = UNSET
        else:
            pinned = self.pinned


        field_dict: dict[str, Any] = {}

        field_dict.update({
        })
        if title is not UNSET:
            field_dict["title"] = title
        if pinned is not UNSET:
            field_dict["pinned"] = pinned

        return field_dict



    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        def _parse_title(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        title = _parse_title(d.pop("title", UNSET))


        def _parse_pinned(data: object) -> bool | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        pinned = _parse_pinned(d.pop("pinned", UNSET))


        conversation_patch = cls(
            title=title,
            pinned=pinned,
        )

        return conversation_patch


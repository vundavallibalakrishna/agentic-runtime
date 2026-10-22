from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast

if TYPE_CHECKING:
    from ..models.chat_part import ChatPart


T = TypeVar("T", bound="ChatMessage")


@_attrs_define
class ChatMessage:
    """
    Attributes:
        role (str):
        content (list[ChatPart] | None | str | Unset):
    """

    role: str
    content: list[ChatPart] | None | str | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        from ..models.chat_part import ChatPart  # noqa: PLC0415

        role = self.role

        content: list[dict[str, Any]] | None | str | Unset
        if isinstance(self.content, Unset):
            content = UNSET
        elif isinstance(self.content, list):
            content = []
            for content_type_1_item_data in self.content:
                content_type_1_item = content_type_1_item_data.to_dict()
                content.append(content_type_1_item)

        else:
            content = self.content

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "role": role,
            }
        )
        if content is not UNSET:
            field_dict["content"] = content

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.chat_part import ChatPart  # noqa: PLC0415

        d = dict(src_dict)
        role = d.pop("role")

        def _parse_content(data: object) -> list[ChatPart] | None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                content_type_1 = []
                _content_type_1 = data
                for content_type_1_item_data in _content_type_1:
                    content_type_1_item = ChatPart.from_dict(content_type_1_item_data)

                    content_type_1.append(content_type_1_item)

                return content_type_1
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(list[ChatPart] | None | str | Unset, data)

        content = _parse_content(d.pop("content", UNSET))

        chat_message = cls(
            role=role,
            content=content,
        )

        return chat_message

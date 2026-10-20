from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast

if TYPE_CHECKING:
  from ..models.alias_test_body_messages_item import AliasTestBodyMessagesItem





T = TypeVar("T", bound="AliasTestBody")



@_attrs_define
class AliasTestBody:
    """ 
        Attributes:
            messages (list[AliasTestBodyMessagesItem] | Unset):
     """

    messages: list[AliasTestBodyMessagesItem] | Unset = UNSET





    def to_dict(self) -> dict[str, Any]:
        from ..models.alias_test_body_messages_item import AliasTestBodyMessagesItem # noqa: PLC0415
        messages: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.messages, Unset):
            messages = []
            for messages_item_data in self.messages:
                messages_item = messages_item_data.to_dict()
                messages.append(messages_item)




        field_dict: dict[str, Any] = {}

        field_dict.update({
        })
        if messages is not UNSET:
            field_dict["messages"] = messages

        return field_dict



    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.alias_test_body_messages_item import AliasTestBodyMessagesItem # noqa: PLC0415
        d = dict(src_dict)
        _messages = d.pop("messages", UNSET)
        messages: list[AliasTestBodyMessagesItem] | Unset = UNSET
        if _messages is not UNSET:
            messages = []
            for messages_item_data in _messages:
                messages_item = AliasTestBodyMessagesItem.from_dict(messages_item_data)



                messages.append(messages_item)


        alias_test_body = cls(
            messages=messages,
        )

        return alias_test_body


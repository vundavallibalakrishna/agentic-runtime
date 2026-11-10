from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast
from uuid import UUID


T = TypeVar("T", bound="WidgetMessageBody")


@_attrs_define
class WidgetMessageBody:
    """
    Attributes:
        text (str):
        attachment_ids (list[UUID] | Unset):
        suggest_followups (bool | Unset):  Default: False.
    """

    text: str
    attachment_ids: list[UUID] | Unset = UNSET
    suggest_followups: bool | Unset = False

    def to_dict(self) -> dict[str, Any]:
        text = self.text

        attachment_ids: list[str] | Unset = UNSET
        if not isinstance(self.attachment_ids, Unset):
            attachment_ids = []
            for attachment_ids_item_data in self.attachment_ids:
                attachment_ids_item = str(attachment_ids_item_data)
                attachment_ids.append(attachment_ids_item)

        suggest_followups = self.suggest_followups

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "text": text,
            }
        )
        if attachment_ids is not UNSET:
            field_dict["attachmentIds"] = attachment_ids
        if suggest_followups is not UNSET:
            field_dict["suggestFollowups"] = suggest_followups

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        text = d.pop("text")

        _attachment_ids = d.pop("attachmentIds", UNSET)
        attachment_ids: list[UUID] | Unset = UNSET
        if _attachment_ids is not UNSET:
            attachment_ids = []
            for attachment_ids_item_data in _attachment_ids:
                attachment_ids_item = UUID(attachment_ids_item_data)

                attachment_ids.append(attachment_ids_item)

        suggest_followups = d.pop("suggestFollowups", UNSET)

        widget_message_body = cls(
            text=text,
            attachment_ids=attachment_ids,
            suggest_followups=suggest_followups,
        )

        return widget_message_body

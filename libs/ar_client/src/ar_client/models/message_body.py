from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast
from uuid import UUID

if TYPE_CHECKING:
    from ..models.message_body_response_format_type_0 import MessageBodyResponseFormatType0


T = TypeVar("T", bound="MessageBody")


@_attrs_define
class MessageBody:
    """
    Attributes:
        text (str):
        attachment_ids (list[UUID] | Unset):
        research_mode (bool | Unset):  Default: False.
        suggest_followups (bool | Unset):  Default: False.
        response_format (MessageBodyResponseFormatType0 | None | Unset):
    """

    text: str
    attachment_ids: list[UUID] | Unset = UNSET
    research_mode: bool | Unset = False
    suggest_followups: bool | Unset = False
    response_format: MessageBodyResponseFormatType0 | None | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        from ..models.message_body_response_format_type_0 import MessageBodyResponseFormatType0  # noqa: PLC0415

        text = self.text

        attachment_ids: list[str] | Unset = UNSET
        if not isinstance(self.attachment_ids, Unset):
            attachment_ids = []
            for attachment_ids_item_data in self.attachment_ids:
                attachment_ids_item = str(attachment_ids_item_data)
                attachment_ids.append(attachment_ids_item)

        research_mode = self.research_mode

        suggest_followups = self.suggest_followups

        response_format: dict[str, Any] | None | Unset
        if isinstance(self.response_format, Unset):
            response_format = UNSET
        elif isinstance(self.response_format, MessageBodyResponseFormatType0):
            response_format = self.response_format.to_dict()
        else:
            response_format = self.response_format

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "text": text,
            }
        )
        if attachment_ids is not UNSET:
            field_dict["attachmentIds"] = attachment_ids
        if research_mode is not UNSET:
            field_dict["researchMode"] = research_mode
        if suggest_followups is not UNSET:
            field_dict["suggestFollowups"] = suggest_followups
        if response_format is not UNSET:
            field_dict["responseFormat"] = response_format

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.message_body_response_format_type_0 import MessageBodyResponseFormatType0  # noqa: PLC0415

        d = dict(src_dict)
        text = d.pop("text")

        _attachment_ids = d.pop("attachmentIds", UNSET)
        attachment_ids: list[UUID] | Unset = UNSET
        if _attachment_ids is not UNSET:
            attachment_ids = []
            for attachment_ids_item_data in _attachment_ids:
                attachment_ids_item = UUID(attachment_ids_item_data)

                attachment_ids.append(attachment_ids_item)

        research_mode = d.pop("researchMode", UNSET)

        suggest_followups = d.pop("suggestFollowups", UNSET)

        def _parse_response_format(data: object) -> MessageBodyResponseFormatType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                response_format_type_0 = MessageBodyResponseFormatType0.from_dict(data)

                return response_format_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(MessageBodyResponseFormatType0 | None | Unset, data)

        response_format = _parse_response_format(d.pop("responseFormat", UNSET))

        message_body = cls(
            text=text,
            attachment_ids=attachment_ids,
            research_mode=research_mode,
            suggest_followups=suggest_followups,
            response_format=response_format,
        )

        return message_body

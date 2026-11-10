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
    from ..models.send_body_response_format_type_0 import SendBodyResponseFormatType0


T = TypeVar("T", bound="SendBody")


@_attrs_define
class SendBody:
    """
    Attributes:
        text (str):
        stream (bool | Unset):  Default: False.
        attachment_ids (list[UUID] | Unset):
        response_format (None | SendBodyResponseFormatType0 | Unset):
        suggest_followups (bool | Unset):  Default: False.
    """

    text: str
    stream: bool | Unset = False
    attachment_ids: list[UUID] | Unset = UNSET
    response_format: None | SendBodyResponseFormatType0 | Unset = UNSET
    suggest_followups: bool | Unset = False

    def to_dict(self) -> dict[str, Any]:
        from ..models.send_body_response_format_type_0 import SendBodyResponseFormatType0  # noqa: PLC0415

        text = self.text

        stream = self.stream

        attachment_ids: list[str] | Unset = UNSET
        if not isinstance(self.attachment_ids, Unset):
            attachment_ids = []
            for attachment_ids_item_data in self.attachment_ids:
                attachment_ids_item = str(attachment_ids_item_data)
                attachment_ids.append(attachment_ids_item)

        response_format: dict[str, Any] | None | Unset
        if isinstance(self.response_format, Unset):
            response_format = UNSET
        elif isinstance(self.response_format, SendBodyResponseFormatType0):
            response_format = self.response_format.to_dict()
        else:
            response_format = self.response_format

        suggest_followups = self.suggest_followups

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "text": text,
            }
        )
        if stream is not UNSET:
            field_dict["stream"] = stream
        if attachment_ids is not UNSET:
            field_dict["attachmentIds"] = attachment_ids
        if response_format is not UNSET:
            field_dict["responseFormat"] = response_format
        if suggest_followups is not UNSET:
            field_dict["suggestFollowups"] = suggest_followups

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.send_body_response_format_type_0 import SendBodyResponseFormatType0  # noqa: PLC0415

        d = dict(src_dict)
        text = d.pop("text")

        stream = d.pop("stream", UNSET)

        _attachment_ids = d.pop("attachmentIds", UNSET)
        attachment_ids: list[UUID] | Unset = UNSET
        if _attachment_ids is not UNSET:
            attachment_ids = []
            for attachment_ids_item_data in _attachment_ids:
                attachment_ids_item = UUID(attachment_ids_item_data)

                attachment_ids.append(attachment_ids_item)

        def _parse_response_format(data: object) -> None | SendBodyResponseFormatType0 | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                response_format_type_0 = SendBodyResponseFormatType0.from_dict(data)

                return response_format_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(None | SendBodyResponseFormatType0 | Unset, data)

        response_format = _parse_response_format(d.pop("responseFormat", UNSET))

        suggest_followups = d.pop("suggestFollowups", UNSET)

        send_body = cls(
            text=text,
            stream=stream,
            attachment_ids=attachment_ids,
            response_format=response_format,
            suggest_followups=suggest_followups,
        )

        return send_body

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset


T = TypeVar("T", bound="ChannelEventBody")


@_attrs_define
class ChannelEventBody:
    """
    Attributes:
        event (str | Unset):  Default: 'channel_event'.
        integration_id (str | Unset):  Default: ''.
        external_event_id (str | Unset):  Default: ''.
        message_id (str | Unset):  Default: ''.
    """

    event: str | Unset = "channel_event"
    integration_id: str | Unset = ""
    external_event_id: str | Unset = ""
    message_id: str | Unset = ""

    def to_dict(self) -> dict[str, Any]:
        event = self.event

        integration_id = self.integration_id

        external_event_id = self.external_event_id

        message_id = self.message_id

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if event is not UNSET:
            field_dict["event"] = event
        if integration_id is not UNSET:
            field_dict["integrationId"] = integration_id
        if external_event_id is not UNSET:
            field_dict["externalEventId"] = external_event_id
        if message_id is not UNSET:
            field_dict["messageId"] = message_id

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        event = d.pop("event", UNSET)

        integration_id = d.pop("integrationId", UNSET)

        external_event_id = d.pop("externalEventId", UNSET)

        message_id = d.pop("messageId", UNSET)

        channel_event_body = cls(
            event=event,
            integration_id=integration_id,
            external_event_id=external_event_id,
            message_id=message_id,
        )

        return channel_event_body

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
    from ..models.inbound_body_command_type_0 import InboundBodyCommandType0


T = TypeVar("T", bound="InboundBody")


@_attrs_define
class InboundBody:
    """
    Attributes:
        integration_id (UUID):
        kind (str):
        event_id (str | Unset):  Default: ''.
        external_user_id (str | Unset):  Default: ''.
        external_user_email (None | str | Unset):
        external_channel_id (str | Unset):  Default: ''.
        external_thread_id (str | Unset):  Default: ''.
        external_message_id (str | Unset):  Default: ''.
        text (str | Unset):  Default: ''.
        is_dm (bool | Unset):  Default: False.
        mentions_bot (bool | Unset):  Default: False.
        command (InboundBodyCommandType0 | None | Unset):
    """

    integration_id: UUID
    kind: str
    event_id: str | Unset = ""
    external_user_id: str | Unset = ""
    external_user_email: None | str | Unset = UNSET
    external_channel_id: str | Unset = ""
    external_thread_id: str | Unset = ""
    external_message_id: str | Unset = ""
    text: str | Unset = ""
    is_dm: bool | Unset = False
    mentions_bot: bool | Unset = False
    command: InboundBodyCommandType0 | None | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        from ..models.inbound_body_command_type_0 import InboundBodyCommandType0  # noqa: PLC0415

        integration_id = str(self.integration_id)

        kind = self.kind

        event_id = self.event_id

        external_user_id = self.external_user_id

        external_user_email: None | str | Unset
        if isinstance(self.external_user_email, Unset):
            external_user_email = UNSET
        else:
            external_user_email = self.external_user_email

        external_channel_id = self.external_channel_id

        external_thread_id = self.external_thread_id

        external_message_id = self.external_message_id

        text = self.text

        is_dm = self.is_dm

        mentions_bot = self.mentions_bot

        command: dict[str, Any] | None | Unset
        if isinstance(self.command, Unset):
            command = UNSET
        elif isinstance(self.command, InboundBodyCommandType0):
            command = self.command.to_dict()
        else:
            command = self.command

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "integrationId": integration_id,
                "kind": kind,
            }
        )
        if event_id is not UNSET:
            field_dict["eventId"] = event_id
        if external_user_id is not UNSET:
            field_dict["externalUserId"] = external_user_id
        if external_user_email is not UNSET:
            field_dict["externalUserEmail"] = external_user_email
        if external_channel_id is not UNSET:
            field_dict["externalChannelId"] = external_channel_id
        if external_thread_id is not UNSET:
            field_dict["externalThreadId"] = external_thread_id
        if external_message_id is not UNSET:
            field_dict["externalMessageId"] = external_message_id
        if text is not UNSET:
            field_dict["text"] = text
        if is_dm is not UNSET:
            field_dict["isDm"] = is_dm
        if mentions_bot is not UNSET:
            field_dict["mentionsBot"] = mentions_bot
        if command is not UNSET:
            field_dict["command"] = command

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.inbound_body_command_type_0 import InboundBodyCommandType0  # noqa: PLC0415

        d = dict(src_dict)
        integration_id = UUID(d.pop("integrationId"))

        kind = d.pop("kind")

        event_id = d.pop("eventId", UNSET)

        external_user_id = d.pop("externalUserId", UNSET)

        def _parse_external_user_email(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        external_user_email = _parse_external_user_email(d.pop("externalUserEmail", UNSET))

        external_channel_id = d.pop("externalChannelId", UNSET)

        external_thread_id = d.pop("externalThreadId", UNSET)

        external_message_id = d.pop("externalMessageId", UNSET)

        text = d.pop("text", UNSET)

        is_dm = d.pop("isDm", UNSET)

        mentions_bot = d.pop("mentionsBot", UNSET)

        def _parse_command(data: object) -> InboundBodyCommandType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                command_type_0 = InboundBodyCommandType0.from_dict(data)

                return command_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(InboundBodyCommandType0 | None | Unset, data)

        command = _parse_command(d.pop("command", UNSET))

        inbound_body = cls(
            integration_id=integration_id,
            kind=kind,
            event_id=event_id,
            external_user_id=external_user_id,
            external_user_email=external_user_email,
            external_channel_id=external_channel_id,
            external_thread_id=external_thread_id,
            external_message_id=external_message_id,
            text=text,
            is_dm=is_dm,
            mentions_bot=mentions_bot,
            command=command,
        )

        return inbound_body

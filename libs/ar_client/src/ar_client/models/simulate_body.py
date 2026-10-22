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
    from ..models.simulate_body_args import SimulateBodyArgs


T = TypeVar("T", bound="SimulateBody")


@_attrs_define
class SimulateBody:
    """
    Attributes:
        tool_qualified_name (str | Unset):  Default: ''.
        tool_call_id (None | Unset | UUID):
        agent_id (None | Unset | UUID):
        user_id (None | Unset | UUID):
        args (SimulateBodyArgs | Unset):
        include_drafts (list[UUID] | Unset):
        trigger (str | Unset):  Default: 'chat'.
        channel (str | Unset):  Default: 'web'.
    """

    tool_qualified_name: str | Unset = ""
    tool_call_id: None | Unset | UUID = UNSET
    agent_id: None | Unset | UUID = UNSET
    user_id: None | Unset | UUID = UNSET
    args: SimulateBodyArgs | Unset = UNSET
    include_drafts: list[UUID] | Unset = UNSET
    trigger: str | Unset = "chat"
    channel: str | Unset = "web"

    def to_dict(self) -> dict[str, Any]:
        from ..models.simulate_body_args import SimulateBodyArgs  # noqa: PLC0415

        tool_qualified_name = self.tool_qualified_name

        tool_call_id: None | str | Unset
        if isinstance(self.tool_call_id, Unset):
            tool_call_id = UNSET
        elif isinstance(self.tool_call_id, UUID):
            tool_call_id = str(self.tool_call_id)
        else:
            tool_call_id = self.tool_call_id

        agent_id: None | str | Unset
        if isinstance(self.agent_id, Unset):
            agent_id = UNSET
        elif isinstance(self.agent_id, UUID):
            agent_id = str(self.agent_id)
        else:
            agent_id = self.agent_id

        user_id: None | str | Unset
        if isinstance(self.user_id, Unset):
            user_id = UNSET
        elif isinstance(self.user_id, UUID):
            user_id = str(self.user_id)
        else:
            user_id = self.user_id

        args: dict[str, Any] | Unset = UNSET
        if not isinstance(self.args, Unset):
            args = self.args.to_dict()

        include_drafts: list[str] | Unset = UNSET
        if not isinstance(self.include_drafts, Unset):
            include_drafts = []
            for include_drafts_item_data in self.include_drafts:
                include_drafts_item = str(include_drafts_item_data)
                include_drafts.append(include_drafts_item)

        trigger = self.trigger

        channel = self.channel

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if tool_qualified_name is not UNSET:
            field_dict["toolQualifiedName"] = tool_qualified_name
        if tool_call_id is not UNSET:
            field_dict["toolCallId"] = tool_call_id
        if agent_id is not UNSET:
            field_dict["agentId"] = agent_id
        if user_id is not UNSET:
            field_dict["userId"] = user_id
        if args is not UNSET:
            field_dict["args"] = args
        if include_drafts is not UNSET:
            field_dict["includeDrafts"] = include_drafts
        if trigger is not UNSET:
            field_dict["trigger"] = trigger
        if channel is not UNSET:
            field_dict["channel"] = channel

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.simulate_body_args import SimulateBodyArgs  # noqa: PLC0415

        d = dict(src_dict)
        tool_qualified_name = d.pop("toolQualifiedName", UNSET)

        def _parse_tool_call_id(data: object) -> None | Unset | UUID:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                tool_call_id_type_0 = UUID(data)

                return tool_call_id_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(None | Unset | UUID, data)

        tool_call_id = _parse_tool_call_id(d.pop("toolCallId", UNSET))

        def _parse_agent_id(data: object) -> None | Unset | UUID:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                agent_id_type_0 = UUID(data)

                return agent_id_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(None | Unset | UUID, data)

        agent_id = _parse_agent_id(d.pop("agentId", UNSET))

        def _parse_user_id(data: object) -> None | Unset | UUID:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                user_id_type_0 = UUID(data)

                return user_id_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(None | Unset | UUID, data)

        user_id = _parse_user_id(d.pop("userId", UNSET))

        _args = d.pop("args", UNSET)
        args: SimulateBodyArgs | Unset
        if isinstance(_args, Unset):
            args = UNSET
        else:
            args = SimulateBodyArgs.from_dict(_args)

        _include_drafts = d.pop("includeDrafts", UNSET)
        include_drafts: list[UUID] | Unset = UNSET
        if _include_drafts is not UNSET:
            include_drafts = []
            for include_drafts_item_data in _include_drafts:
                include_drafts_item = UUID(include_drafts_item_data)

                include_drafts.append(include_drafts_item)

        trigger = d.pop("trigger", UNSET)

        channel = d.pop("channel", UNSET)

        simulate_body = cls(
            tool_qualified_name=tool_qualified_name,
            tool_call_id=tool_call_id,
            agent_id=agent_id,
            user_id=user_id,
            args=args,
            include_drafts=include_drafts,
            trigger=trigger,
            channel=channel,
        )

        return simulate_body

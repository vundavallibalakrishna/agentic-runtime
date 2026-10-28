from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from uuid import UUID


T = TypeVar("T", bound="WidgetConversationBody")


@_attrs_define
class WidgetConversationBody:
    """
    Attributes:
        agent_id (UUID):
    """

    agent_id: UUID

    def to_dict(self) -> dict[str, Any]:
        agent_id = str(self.agent_id)

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "agentId": agent_id,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        agent_id = UUID(d.pop("agentId"))

        widget_conversation_body = cls(
            agent_id=agent_id,
        )

        return widget_conversation_body

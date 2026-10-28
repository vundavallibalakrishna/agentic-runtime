from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast
from uuid import UUID


T = TypeVar("T", bound="GovernanceExportBody")


@_attrs_define
class GovernanceExportBody:
    """
    Attributes:
        agent_ids (list[UUID] | Unset):
    """

    agent_ids: list[UUID] | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        agent_ids: list[str] | Unset = UNSET
        if not isinstance(self.agent_ids, Unset):
            agent_ids = []
            for agent_ids_item_data in self.agent_ids:
                agent_ids_item = str(agent_ids_item_data)
                agent_ids.append(agent_ids_item)

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if agent_ids is not UNSET:
            field_dict["agentIds"] = agent_ids

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        _agent_ids = d.pop("agentIds", UNSET)
        agent_ids: list[UUID] | Unset = UNSET
        if _agent_ids is not UNSET:
            agent_ids = []
            for agent_ids_item_data in _agent_ids:
                agent_ids_item = UUID(agent_ids_item_data)

                agent_ids.append(agent_ids_item)

        governance_export_body = cls(
            agent_ids=agent_ids,
        )

        return governance_export_body

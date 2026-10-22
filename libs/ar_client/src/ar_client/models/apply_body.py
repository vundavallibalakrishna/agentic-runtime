from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define

from ..types import UNSET, Unset

T = TypeVar("T", bound="ApplyBody")


@_attrs_define
class ApplyBody:
    """
    Attributes:
        mode (str | Unset):  Default: 'create'.
        agent_id (None | Unset | UUID):
    """

    mode: str | Unset = "create"
    agent_id: Unset | UUID | None = UNSET

    def to_dict(self) -> dict[str, Any]:
        mode = self.mode

        agent_id: str | Unset | None
        if isinstance(self.agent_id, Unset):
            agent_id = UNSET
        elif isinstance(self.agent_id, UUID):
            agent_id = str(self.agent_id)
        else:
            agent_id = self.agent_id

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if mode is not UNSET:
            field_dict["mode"] = mode
        if agent_id is not UNSET:
            field_dict["agentId"] = agent_id

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        mode = d.pop("mode", UNSET)

        def _parse_agent_id(data: object) -> Unset | UUID | None:
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
            return cast("None | Unset | UUID", data)

        agent_id = _parse_agent_id(d.pop("agentId", UNSET))

        apply_body = cls(
            mode=mode,
            agent_id=agent_id,
        )

        return apply_body

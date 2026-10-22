from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast
from uuid import UUID
import datetime

if TYPE_CHECKING:
    from ..models.standing_body_argument_constraints_item import StandingBodyArgumentConstraintsItem


T = TypeVar("T", bound="StandingBody")


@_attrs_define
class StandingBody:
    """
    Attributes:
        tool_id (UUID):
        expires_at (datetime.datetime):
        agent_id (None | Unset | UUID):
        routine_id (None | Unset | UUID):
        argument_constraints (list[StandingBodyArgumentConstraintsItem] | Unset):
        max_uses (int | None | Unset):
    """

    tool_id: UUID
    expires_at: datetime.datetime
    agent_id: None | Unset | UUID = UNSET
    routine_id: None | Unset | UUID = UNSET
    argument_constraints: list[StandingBodyArgumentConstraintsItem] | Unset = UNSET
    max_uses: int | None | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        from ..models.standing_body_argument_constraints_item import (
            StandingBodyArgumentConstraintsItem,
        )  # noqa: PLC0415

        tool_id = str(self.tool_id)

        expires_at = self.expires_at.isoformat()

        agent_id: None | str | Unset
        if isinstance(self.agent_id, Unset):
            agent_id = UNSET
        elif isinstance(self.agent_id, UUID):
            agent_id = str(self.agent_id)
        else:
            agent_id = self.agent_id

        routine_id: None | str | Unset
        if isinstance(self.routine_id, Unset):
            routine_id = UNSET
        elif isinstance(self.routine_id, UUID):
            routine_id = str(self.routine_id)
        else:
            routine_id = self.routine_id

        argument_constraints: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.argument_constraints, Unset):
            argument_constraints = []
            for argument_constraints_item_data in self.argument_constraints:
                argument_constraints_item = argument_constraints_item_data.to_dict()
                argument_constraints.append(argument_constraints_item)

        max_uses: int | None | Unset
        if isinstance(self.max_uses, Unset):
            max_uses = UNSET
        else:
            max_uses = self.max_uses

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "toolId": tool_id,
                "expiresAt": expires_at,
            }
        )
        if agent_id is not UNSET:
            field_dict["agentId"] = agent_id
        if routine_id is not UNSET:
            field_dict["routineId"] = routine_id
        if argument_constraints is not UNSET:
            field_dict["argumentConstraints"] = argument_constraints
        if max_uses is not UNSET:
            field_dict["maxUses"] = max_uses

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.standing_body_argument_constraints_item import (
            StandingBodyArgumentConstraintsItem,
        )  # noqa: PLC0415

        d = dict(src_dict)
        tool_id = UUID(d.pop("toolId"))

        expires_at = datetime.datetime.fromisoformat(d.pop("expiresAt"))

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

        def _parse_routine_id(data: object) -> None | Unset | UUID:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                routine_id_type_0 = UUID(data)

                return routine_id_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(None | Unset | UUID, data)

        routine_id = _parse_routine_id(d.pop("routineId", UNSET))

        _argument_constraints = d.pop("argumentConstraints", UNSET)
        argument_constraints: list[StandingBodyArgumentConstraintsItem] | Unset = UNSET
        if _argument_constraints is not UNSET:
            argument_constraints = []
            for argument_constraints_item_data in _argument_constraints:
                argument_constraints_item = StandingBodyArgumentConstraintsItem.from_dict(
                    argument_constraints_item_data
                )

                argument_constraints.append(argument_constraints_item)

        def _parse_max_uses(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        max_uses = _parse_max_uses(d.pop("maxUses", UNSET))

        standing_body = cls(
            tool_id=tool_id,
            expires_at=expires_at,
            agent_id=agent_id,
            routine_id=routine_id,
            argument_constraints=argument_constraints,
            max_uses=max_uses,
        )

        return standing_body

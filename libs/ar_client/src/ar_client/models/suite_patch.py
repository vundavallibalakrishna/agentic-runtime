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
    from ..models.suite_patch_gate_type_0 import SuitePatchGateType0


T = TypeVar("T", bound="SuitePatch")


@_attrs_define
class SuitePatch:
    """
    Attributes:
        name (None | str | Unset):
        description (None | str | Unset):
        kind (None | str | Unset):
        agent_id (None | Unset | UUID):
        gate (None | SuitePatchGateType0 | Unset):
    """

    name: None | str | Unset = UNSET
    description: None | str | Unset = UNSET
    kind: None | str | Unset = UNSET
    agent_id: None | Unset | UUID = UNSET
    gate: None | SuitePatchGateType0 | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        from ..models.suite_patch_gate_type_0 import SuitePatchGateType0  # noqa: PLC0415

        name: None | str | Unset
        if isinstance(self.name, Unset):
            name = UNSET
        else:
            name = self.name

        description: None | str | Unset
        if isinstance(self.description, Unset):
            description = UNSET
        else:
            description = self.description

        kind: None | str | Unset
        if isinstance(self.kind, Unset):
            kind = UNSET
        else:
            kind = self.kind

        agent_id: None | str | Unset
        if isinstance(self.agent_id, Unset):
            agent_id = UNSET
        elif isinstance(self.agent_id, UUID):
            agent_id = str(self.agent_id)
        else:
            agent_id = self.agent_id

        gate: dict[str, Any] | None | Unset
        if isinstance(self.gate, Unset):
            gate = UNSET
        elif isinstance(self.gate, SuitePatchGateType0):
            gate = self.gate.to_dict()
        else:
            gate = self.gate

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if name is not UNSET:
            field_dict["name"] = name
        if description is not UNSET:
            field_dict["description"] = description
        if kind is not UNSET:
            field_dict["kind"] = kind
        if agent_id is not UNSET:
            field_dict["agentId"] = agent_id
        if gate is not UNSET:
            field_dict["gate"] = gate

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.suite_patch_gate_type_0 import SuitePatchGateType0  # noqa: PLC0415

        d = dict(src_dict)

        def _parse_name(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        name = _parse_name(d.pop("name", UNSET))

        def _parse_description(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        description = _parse_description(d.pop("description", UNSET))

        def _parse_kind(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        kind = _parse_kind(d.pop("kind", UNSET))

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

        def _parse_gate(data: object) -> None | SuitePatchGateType0 | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                gate_type_0 = SuitePatchGateType0.from_dict(data)

                return gate_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(None | SuitePatchGateType0 | Unset, data)

        gate = _parse_gate(d.pop("gate", UNSET))

        suite_patch = cls(
            name=name,
            description=description,
            kind=kind,
            agent_id=agent_id,
            gate=gate,
        )

        return suite_patch

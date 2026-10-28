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
    from ..models.suite_body_gate_type_0 import SuiteBodyGateType0


T = TypeVar("T", bound="SuiteBody")


@_attrs_define
class SuiteBody:
    """
    Attributes:
        name (str):
        description (str | Unset):  Default: ''.
        kind (str | Unset):  Default: 'functional'.
        agent_id (None | Unset | UUID):
        gate (None | SuiteBodyGateType0 | Unset):
    """

    name: str
    description: str | Unset = ""
    kind: str | Unset = "functional"
    agent_id: None | Unset | UUID = UNSET
    gate: None | SuiteBodyGateType0 | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        from ..models.suite_body_gate_type_0 import SuiteBodyGateType0  # noqa: PLC0415

        name = self.name

        description = self.description

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
        elif isinstance(self.gate, SuiteBodyGateType0):
            gate = self.gate.to_dict()
        else:
            gate = self.gate

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "name": name,
            }
        )
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
        from ..models.suite_body_gate_type_0 import SuiteBodyGateType0  # noqa: PLC0415

        d = dict(src_dict)
        name = d.pop("name")

        description = d.pop("description", UNSET)

        kind = d.pop("kind", UNSET)

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

        def _parse_gate(data: object) -> None | SuiteBodyGateType0 | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                gate_type_0 = SuiteBodyGateType0.from_dict(data)

                return gate_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(None | SuiteBodyGateType0 | Unset, data)

        gate = _parse_gate(d.pop("gate", UNSET))

        suite_body = cls(
            name=name,
            description=description,
            kind=kind,
            agent_id=agent_id,
            gate=gate,
        )

        return suite_body

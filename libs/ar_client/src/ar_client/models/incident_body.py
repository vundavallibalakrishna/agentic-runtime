from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast
from uuid import UUID


T = TypeVar("T", bound="IncidentBody")


@_attrs_define
class IncidentBody:
    """
    Attributes:
        severity (str):
        summary (str):
        agent_id (None | Unset | UUID):
        agent_version_id (None | Unset | UUID):
        run_id (None | Unset | UUID):
    """

    severity: str
    summary: str
    agent_id: None | Unset | UUID = UNSET
    agent_version_id: None | Unset | UUID = UNSET
    run_id: None | Unset | UUID = UNSET

    def to_dict(self) -> dict[str, Any]:
        severity = self.severity

        summary = self.summary

        agent_id: None | str | Unset
        if isinstance(self.agent_id, Unset):
            agent_id = UNSET
        elif isinstance(self.agent_id, UUID):
            agent_id = str(self.agent_id)
        else:
            agent_id = self.agent_id

        agent_version_id: None | str | Unset
        if isinstance(self.agent_version_id, Unset):
            agent_version_id = UNSET
        elif isinstance(self.agent_version_id, UUID):
            agent_version_id = str(self.agent_version_id)
        else:
            agent_version_id = self.agent_version_id

        run_id: None | str | Unset
        if isinstance(self.run_id, Unset):
            run_id = UNSET
        elif isinstance(self.run_id, UUID):
            run_id = str(self.run_id)
        else:
            run_id = self.run_id

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "severity": severity,
                "summary": summary,
            }
        )
        if agent_id is not UNSET:
            field_dict["agentId"] = agent_id
        if agent_version_id is not UNSET:
            field_dict["agentVersionId"] = agent_version_id
        if run_id is not UNSET:
            field_dict["runId"] = run_id

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        severity = d.pop("severity")

        summary = d.pop("summary")

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

        def _parse_agent_version_id(data: object) -> None | Unset | UUID:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                agent_version_id_type_0 = UUID(data)

                return agent_version_id_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(None | Unset | UUID, data)

        agent_version_id = _parse_agent_version_id(d.pop("agentVersionId", UNSET))

        def _parse_run_id(data: object) -> None | Unset | UUID:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                run_id_type_0 = UUID(data)

                return run_id_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(None | Unset | UUID, data)

        run_id = _parse_run_id(d.pop("runId", UNSET))

        incident_body = cls(
            severity=severity,
            summary=summary,
            agent_id=agent_id,
            agent_version_id=agent_version_id,
            run_id=run_id,
        )

        return incident_body

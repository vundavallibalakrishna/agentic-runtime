from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast


T = TypeVar("T", bound="IncidentPatch")


@_attrs_define
class IncidentPatch:
    """
    Attributes:
        status (None | str | Unset):
        summary (None | str | Unset):
        severity (None | str | Unset):
    """

    status: None | str | Unset = UNSET
    summary: None | str | Unset = UNSET
    severity: None | str | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        status: None | str | Unset
        if isinstance(self.status, Unset):
            status = UNSET
        else:
            status = self.status

        summary: None | str | Unset
        if isinstance(self.summary, Unset):
            summary = UNSET
        else:
            summary = self.summary

        severity: None | str | Unset
        if isinstance(self.severity, Unset):
            severity = UNSET
        else:
            severity = self.severity

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if status is not UNSET:
            field_dict["status"] = status
        if summary is not UNSET:
            field_dict["summary"] = summary
        if severity is not UNSET:
            field_dict["severity"] = severity

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)

        def _parse_status(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        status = _parse_status(d.pop("status", UNSET))

        def _parse_summary(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        summary = _parse_summary(d.pop("summary", UNSET))

        def _parse_severity(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        severity = _parse_severity(d.pop("severity", UNSET))

        incident_patch = cls(
            status=status,
            summary=summary,
            severity=severity,
        )

        return incident_patch

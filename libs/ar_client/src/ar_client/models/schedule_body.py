from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset


T = TypeVar("T", bound="ScheduleBody")


@_attrs_define
class ScheduleBody:
    """
    Attributes:
        retention_days (int):
        disposition (str):
    """

    retention_days: int
    disposition: str

    def to_dict(self) -> dict[str, Any]:
        retention_days = self.retention_days

        disposition = self.disposition

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "retentionDays": retention_days,
                "disposition": disposition,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        retention_days = d.pop("retentionDays")

        disposition = d.pop("disposition")

        schedule_body = cls(
            retention_days=retention_days,
            disposition=disposition,
        )

        return schedule_body

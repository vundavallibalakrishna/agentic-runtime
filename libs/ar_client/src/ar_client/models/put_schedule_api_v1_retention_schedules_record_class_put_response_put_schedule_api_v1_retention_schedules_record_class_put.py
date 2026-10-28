from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset


T = TypeVar(
    "T",
    bound="PutScheduleApiV1RetentionSchedulesRecordClassPutResponsePutScheduleApiV1RetentionSchedulesRecordClassPut",
)


@_attrs_define
class PutScheduleApiV1RetentionSchedulesRecordClassPutResponsePutScheduleApiV1RetentionSchedulesRecordClassPut:
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        put_schedule_api_v1_retention_schedules_record_class_put_response_put_schedule_api_v1_retention_schedules_record_class_put = cls()

        put_schedule_api_v1_retention_schedules_record_class_put_response_put_schedule_api_v1_retention_schedules_record_class_put.additional_properties = d
        return put_schedule_api_v1_retention_schedules_record_class_put_response_put_schedule_api_v1_retention_schedules_record_class_put

    @property
    def additional_keys(self) -> list[str]:
        return list(self.additional_properties.keys())

    def __getitem__(self, key: str) -> Any:
        return self.additional_properties[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.additional_properties[key] = value

    def __delitem__(self, key: str) -> None:
        del self.additional_properties[key]

    def __contains__(self, key: str) -> bool:
        return key in self.additional_properties

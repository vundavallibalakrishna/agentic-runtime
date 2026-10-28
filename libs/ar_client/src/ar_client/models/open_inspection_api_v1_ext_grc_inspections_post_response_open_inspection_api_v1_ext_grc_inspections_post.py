from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset


T = TypeVar(
    "T",
    bound="OpenInspectionApiV1ExtGrcInspectionsPostResponseOpenInspectionApiV1ExtGrcInspectionsPost",
)


@_attrs_define
class OpenInspectionApiV1ExtGrcInspectionsPostResponseOpenInspectionApiV1ExtGrcInspectionsPost:
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        open_inspection_api_v1_ext_grc_inspections_post_response_open_inspection_api_v1_ext_grc_inspections_post = cls()

        open_inspection_api_v1_ext_grc_inspections_post_response_open_inspection_api_v1_ext_grc_inspections_post.additional_properties = d
        return open_inspection_api_v1_ext_grc_inspections_post_response_open_inspection_api_v1_ext_grc_inspections_post

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

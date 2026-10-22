from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define

from ..types import UNSET, Unset

T = TypeVar("T", bound="DescriptionBody")


@_attrs_define
class DescriptionBody:
    """
    Attributes:
        description (str):
        available_only (bool | Unset):  Default: True.
    """

    description: str
    available_only: bool | Unset = True

    def to_dict(self) -> dict[str, Any]:
        description = self.description

        available_only = self.available_only

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "description": description,
            }
        )
        if available_only is not UNSET:
            field_dict["availableOnly"] = available_only

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        description = d.pop("description")

        available_only = d.pop("availableOnly", UNSET)

        description_body = cls(
            description=description,
            available_only=available_only,
        )

        return description_body

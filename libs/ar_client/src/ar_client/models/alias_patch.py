from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from uuid import UUID


T = TypeVar("T", bound="AliasPatch")


@_attrs_define
class AliasPatch:
    """
    Attributes:
        primary_model_id (UUID):
    """

    primary_model_id: UUID

    def to_dict(self) -> dict[str, Any]:
        primary_model_id = str(self.primary_model_id)

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "primaryModelId": primary_model_id,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        primary_model_id = UUID(d.pop("primaryModelId"))

        alias_patch = cls(
            primary_model_id=primary_model_id,
        )

        return alias_patch

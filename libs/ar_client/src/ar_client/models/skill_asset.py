from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from uuid import UUID


T = TypeVar("T", bound="SkillAsset")


@_attrs_define
class SkillAsset:
    """
    Attributes:
        path (str):
        file_id (UUID):
    """

    path: str
    file_id: UUID

    def to_dict(self) -> dict[str, Any]:
        path = self.path

        file_id = str(self.file_id)

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "path": path,
                "fileId": file_id,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        path = d.pop("path")

        file_id = UUID(d.pop("fileId"))

        skill_asset = cls(
            path=path,
            file_id=file_id,
        )

        return skill_asset

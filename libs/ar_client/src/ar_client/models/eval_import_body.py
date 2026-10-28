from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from uuid import UUID


T = TypeVar("T", bound="EvalImportBody")


@_attrs_define
class EvalImportBody:
    """
    Attributes:
        file_id (UUID):
    """

    file_id: UUID

    def to_dict(self) -> dict[str, Any]:
        file_id = str(self.file_id)

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "fileId": file_id,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        file_id = UUID(d.pop("fileId"))

        eval_import_body = cls(
            file_id=file_id,
        )

        return eval_import_body

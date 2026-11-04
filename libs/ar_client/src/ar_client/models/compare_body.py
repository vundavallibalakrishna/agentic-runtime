from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from uuid import UUID


T = TypeVar("T", bound="CompareBody")


@_attrs_define
class CompareBody:
    """
    Attributes:
        other_document_id (UUID):
        model_alias (str | Unset):  Default: ''.
    """

    other_document_id: UUID
    model_alias: str | Unset = ""

    def to_dict(self) -> dict[str, Any]:
        other_document_id = str(self.other_document_id)

        model_alias = self.model_alias

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "otherDocumentId": other_document_id,
            }
        )
        if model_alias is not UNSET:
            field_dict["modelAlias"] = model_alias

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        other_document_id = UUID(d.pop("otherDocumentId"))

        model_alias = d.pop("modelAlias", UNSET)

        compare_body = cls(
            other_document_id=other_document_id,
            model_alias=model_alias,
        )

        return compare_body

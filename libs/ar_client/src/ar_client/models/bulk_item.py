from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from uuid import UUID


T = TypeVar("T", bound="BulkItem")


@_attrs_define
class BulkItem:
    """
    Attributes:
        review_item_id (UUID):
        content_hash (str):
        statement_hash (str):
    """

    review_item_id: UUID
    content_hash: str
    statement_hash: str

    def to_dict(self) -> dict[str, Any]:
        review_item_id = str(self.review_item_id)

        content_hash = self.content_hash

        statement_hash = self.statement_hash

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "reviewItemId": review_item_id,
                "contentHash": content_hash,
                "statementHash": statement_hash,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        review_item_id = UUID(d.pop("reviewItemId"))

        content_hash = d.pop("contentHash")

        statement_hash = d.pop("statementHash")

        bulk_item = cls(
            review_item_id=review_item_id,
            content_hash=content_hash,
            statement_hash=statement_hash,
        )

        return bulk_item

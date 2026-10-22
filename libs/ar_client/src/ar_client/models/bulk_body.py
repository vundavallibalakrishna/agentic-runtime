from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast

if TYPE_CHECKING:
    from ..models.bulk_item import BulkItem


T = TypeVar("T", bound="BulkBody")


@_attrs_define
class BulkBody:
    """
    Attributes:
        decision (str):
        items (list[BulkItem]):
        comment (str | Unset):  Default: ''.
    """

    decision: str
    items: list[BulkItem]
    comment: str | Unset = ""

    def to_dict(self) -> dict[str, Any]:
        from ..models.bulk_item import BulkItem  # noqa: PLC0415

        decision = self.decision

        items = []
        for items_item_data in self.items:
            items_item = items_item_data.to_dict()
            items.append(items_item)

        comment = self.comment

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "decision": decision,
                "items": items,
            }
        )
        if comment is not UNSET:
            field_dict["comment"] = comment

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.bulk_item import BulkItem  # noqa: PLC0415

        d = dict(src_dict)
        decision = d.pop("decision")

        items = []
        _items = d.pop("items")
        for items_item_data in _items:
            items_item = BulkItem.from_dict(items_item_data)

            items.append(items_item)

        comment = d.pop("comment", UNSET)

        bulk_body = cls(
            decision=decision,
            items=items,
            comment=comment,
        )

        return bulk_body

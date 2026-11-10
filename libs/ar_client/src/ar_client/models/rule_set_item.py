from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset


T = TypeVar("T", bound="RuleSetItem")


@_attrs_define
class RuleSetItem:
    """
    Attributes:
        item_id (str | Unset):  Default: ''.
        statement (str | Unset):  Default: ''.
    """

    item_id: str | Unset = ""
    statement: str | Unset = ""

    def to_dict(self) -> dict[str, Any]:
        item_id = self.item_id

        statement = self.statement

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if item_id is not UNSET:
            field_dict["itemId"] = item_id
        if statement is not UNSET:
            field_dict["statement"] = statement

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        item_id = d.pop("itemId", UNSET)

        statement = d.pop("statement", UNSET)

        rule_set_item = cls(
            item_id=item_id,
            statement=statement,
        )

        return rule_set_item

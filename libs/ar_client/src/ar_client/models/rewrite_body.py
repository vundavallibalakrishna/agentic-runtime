from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset


T = TypeVar("T", bound="RewriteBody")


@_attrs_define
class RewriteBody:
    """
    Attributes:
        instruction (str):
        anchor (str | Unset):  Default: ''.
        model_alias (str | Unset):  Default: ''.
    """

    instruction: str
    anchor: str | Unset = ""
    model_alias: str | Unset = ""

    def to_dict(self) -> dict[str, Any]:
        instruction = self.instruction

        anchor = self.anchor

        model_alias = self.model_alias

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "instruction": instruction,
            }
        )
        if anchor is not UNSET:
            field_dict["anchor"] = anchor
        if model_alias is not UNSET:
            field_dict["modelAlias"] = model_alias

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        instruction = d.pop("instruction")

        anchor = d.pop("anchor", UNSET)

        model_alias = d.pop("modelAlias", UNSET)

        rewrite_body = cls(
            instruction=instruction,
            anchor=anchor,
            model_alias=model_alias,
        )

        return rewrite_body

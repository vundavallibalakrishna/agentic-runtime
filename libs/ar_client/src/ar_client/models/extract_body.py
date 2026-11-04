from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast


T = TypeVar("T", bound="ExtractBody")


@_attrs_define
class ExtractBody:
    """
    Attributes:
        fields (list[str] | Unset):
        model_alias (str | Unset):  Default: ''.
    """

    fields: list[str] | Unset = UNSET
    model_alias: str | Unset = ""

    def to_dict(self) -> dict[str, Any]:
        fields: list[str] | Unset = UNSET
        if not isinstance(self.fields, Unset):
            fields = self.fields

        model_alias = self.model_alias

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if fields is not UNSET:
            field_dict["fields"] = fields
        if model_alias is not UNSET:
            field_dict["modelAlias"] = model_alias

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        fields = cast(list[str], d.pop("fields", UNSET))

        model_alias = d.pop("modelAlias", UNSET)

        extract_body = cls(
            fields=fields,
            model_alias=model_alias,
        )

        return extract_body

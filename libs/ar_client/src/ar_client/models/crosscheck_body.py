from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset


T = TypeVar("T", bound="CrosscheckBody")


@_attrs_define
class CrosscheckBody:
    """
    Attributes:
        focus (str | Unset):  Default: ''.
        model_alias (str | Unset):  Default: ''.
    """

    focus: str | Unset = ""
    model_alias: str | Unset = ""

    def to_dict(self) -> dict[str, Any]:
        focus = self.focus

        model_alias = self.model_alias

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if focus is not UNSET:
            field_dict["focus"] = focus
        if model_alias is not UNSET:
            field_dict["modelAlias"] = model_alias

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        focus = d.pop("focus", UNSET)

        model_alias = d.pop("modelAlias", UNSET)

        crosscheck_body = cls(
            focus=focus,
            model_alias=model_alias,
        )

        return crosscheck_body

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset


T = TypeVar("T", bound="ReprocessBody")


@_attrs_define
class ReprocessBody:
    """
    Attributes:
        engine (str | Unset):  Default: ''.
    """

    engine: str | Unset = ""

    def to_dict(self) -> dict[str, Any]:
        engine = self.engine

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if engine is not UNSET:
            field_dict["engine"] = engine

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        engine = d.pop("engine", UNSET)

        reprocess_body = cls(
            engine=engine,
        )

        return reprocess_body

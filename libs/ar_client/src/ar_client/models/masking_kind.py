from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset


T = TypeVar("T", bound="MaskingKind")


@_attrs_define
class MaskingKind:
    """
    Attributes:
        name (str):
        source (str):
        masked (bool):
        default (bool):
    """

    name: str
    source: str
    masked: bool
    default: bool

    def to_dict(self) -> dict[str, Any]:
        name = self.name

        source = self.source

        masked = self.masked

        default = self.default

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "name": name,
                "source": source,
                "masked": masked,
                "default": default,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        name = d.pop("name")

        source = d.pop("source")

        masked = d.pop("masked")

        default = d.pop("default")

        masking_kind = cls(
            name=name,
            source=source,
            masked=masked,
            default=default,
        )

        return masking_kind

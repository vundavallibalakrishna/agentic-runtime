from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from typing import cast


T = TypeVar("T", bound="UploadLimits")


@_attrs_define
class UploadLimits:
    """
    Attributes:
        mime_types (list[str]):
        max_bytes (int):
    """

    mime_types: list[str]
    max_bytes: int

    def to_dict(self) -> dict[str, Any]:
        mime_types = self.mime_types

        max_bytes = self.max_bytes

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "mimeTypes": mime_types,
                "maxBytes": max_bytes,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        mime_types = cast(list[str], d.pop("mimeTypes"))

        max_bytes = d.pop("maxBytes")

        upload_limits = cls(
            mime_types=mime_types,
            max_bytes=max_bytes,
        )

        return upload_limits

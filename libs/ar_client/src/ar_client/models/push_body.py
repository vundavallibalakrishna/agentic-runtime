from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset


T = TypeVar("T", bound="PushBody")


@_attrs_define
class PushBody:
    """
    Attributes:
        endpoint (str):
        content_encoding (str | Unset):  Default: 'aes128gcm'.
    """

    endpoint: str
    content_encoding: str | Unset = "aes128gcm"

    def to_dict(self) -> dict[str, Any]:
        endpoint = self.endpoint

        content_encoding = self.content_encoding

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "endpoint": endpoint,
            }
        )
        if content_encoding is not UNSET:
            field_dict["contentEncoding"] = content_encoding

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        endpoint = d.pop("endpoint")

        content_encoding = d.pop("contentEncoding", UNSET)

        push_body = cls(
            endpoint=endpoint,
            content_encoding=content_encoding,
        )

        return push_body

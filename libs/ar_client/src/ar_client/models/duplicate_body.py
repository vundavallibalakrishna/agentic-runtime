from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset


T = TypeVar("T", bound="DuplicateBody")


@_attrs_define
class DuplicateBody:
    """
    Attributes:
        slug (str):
        name (str):
    """

    slug: str
    name: str

    def to_dict(self) -> dict[str, Any]:
        slug = self.slug

        name = self.name

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "slug": slug,
                "name": name,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        slug = d.pop("slug")

        name = d.pop("name")

        duplicate_body = cls(
            slug=slug,
            name=name,
        )

        return duplicate_body

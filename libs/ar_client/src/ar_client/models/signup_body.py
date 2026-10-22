from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset


T = TypeVar("T", bound="SignupBody")


@_attrs_define
class SignupBody:
    """
    Attributes:
        slug (str):
        name (str):
        email (str):
    """

    slug: str
    name: str
    email: str

    def to_dict(self) -> dict[str, Any]:
        slug = self.slug

        name = self.name

        email = self.email

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "slug": slug,
                "name": name,
                "email": email,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        slug = d.pop("slug")

        name = d.pop("name")

        email = d.pop("email")

        signup_body = cls(
            slug=slug,
            name=name,
            email=email,
        )

        return signup_body

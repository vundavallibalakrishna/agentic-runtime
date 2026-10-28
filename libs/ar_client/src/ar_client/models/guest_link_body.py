from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset


T = TypeVar("T", bound="GuestLinkBody")


@_attrs_define
class GuestLinkBody:
    """
    Attributes:
        email (str):
        tenant_slug (str):
    """

    email: str
    tenant_slug: str

    def to_dict(self) -> dict[str, Any]:
        email = self.email

        tenant_slug = self.tenant_slug

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "email": email,
                "tenantSlug": tenant_slug,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        email = d.pop("email")

        tenant_slug = d.pop("tenantSlug")

        guest_link_body = cls(
            email=email,
            tenant_slug=tenant_slug,
        )

        return guest_link_body

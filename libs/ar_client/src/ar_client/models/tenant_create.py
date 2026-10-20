from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset







T = TypeVar("T", bound="TenantCreate")



@_attrs_define
class TenantCreate:
    """ 
        Attributes:
            slug (str):
            name (str):
            plan_key (str):
            owner_email (str):
     """

    slug: str
    name: str
    plan_key: str
    owner_email: str





    def to_dict(self) -> dict[str, Any]:
        slug = self.slug

        name = self.name

        plan_key = self.plan_key

        owner_email = self.owner_email


        field_dict: dict[str, Any] = {}

        field_dict.update({
            "slug": slug,
            "name": name,
            "planKey": plan_key,
            "ownerEmail": owner_email,
        })

        return field_dict



    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        slug = d.pop("slug")

        name = d.pop("name")

        plan_key = d.pop("planKey")

        owner_email = d.pop("ownerEmail")

        tenant_create = cls(
            slug=slug,
            name=name,
            plan_key=plan_key,
            owner_email=owner_email,
        )

        return tenant_create


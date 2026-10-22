from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset


T = TypeVar("T", bound="ProviderBody")


@_attrs_define
class ProviderBody:
    """
    Attributes:
        name (str):
        base_url (str):
        kind (str | Unset):  Default: 'openai_compatible'.
    """

    name: str
    base_url: str
    kind: str | Unset = "openai_compatible"

    def to_dict(self) -> dict[str, Any]:
        name = self.name

        base_url = self.base_url

        kind = self.kind

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "name": name,
                "baseUrl": base_url,
            }
        )
        if kind is not UNSET:
            field_dict["kind"] = kind

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        name = d.pop("name")

        base_url = d.pop("baseUrl")

        kind = d.pop("kind", UNSET)

        provider_body = cls(
            name=name,
            base_url=base_url,
            kind=kind,
        )

        return provider_body

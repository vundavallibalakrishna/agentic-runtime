from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset






T = TypeVar("T", bound="SecretCreate")



@_attrs_define
class SecretCreate:
    """ 
        Attributes:
            name (str):
            value (str):
            kind (str | Unset):  Default: 'generic'.
            description (str | Unset):  Default: ''.
     """

    name: str
    value: str
    kind: str | Unset = 'generic'
    description: str | Unset = ''





    def to_dict(self) -> dict[str, Any]:
        name = self.name

        value = self.value

        kind = self.kind

        description = self.description


        field_dict: dict[str, Any] = {}

        field_dict.update({
            "name": name,
            "value": value,
        })
        if kind is not UNSET:
            field_dict["kind"] = kind
        if description is not UNSET:
            field_dict["description"] = description

        return field_dict



    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        name = d.pop("name")

        value = d.pop("value")

        kind = d.pop("kind", UNSET)

        description = d.pop("description", UNSET)

        secret_create = cls(
            name=name,
            value=value,
            kind=kind,
            description=description,
        )

        return secret_create


from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast






T = TypeVar("T", bound="InvitationCreate")



@_attrs_define
class InvitationCreate:
    """ 
        Attributes:
            emails (list[str]):
            role_keys (list[str] | Unset):
     """

    emails: list[str]
    role_keys: list[str] | Unset = UNSET





    def to_dict(self) -> dict[str, Any]:
        emails = self.emails



        role_keys: list[str] | Unset = UNSET
        if not isinstance(self.role_keys, Unset):
            role_keys = self.role_keys




        field_dict: dict[str, Any] = {}

        field_dict.update({
            "emails": emails,
        })
        if role_keys is not UNSET:
            field_dict["roleKeys"] = role_keys

        return field_dict



    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        emails = cast(list[str], d.pop("emails"))


        role_keys = cast(list[str], d.pop("roleKeys", UNSET))


        invitation_create = cls(
            emails=emails,
            role_keys=role_keys,
        )

        return invitation_create


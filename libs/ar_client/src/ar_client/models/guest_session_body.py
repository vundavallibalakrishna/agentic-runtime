from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset


T = TypeVar("T", bound="GuestSessionBody")


@_attrs_define
class GuestSessionBody:
    """
    Attributes:
        token (str):
        totp (str | Unset):  Default: ''.
    """

    token: str
    totp: str | Unset = ""

    def to_dict(self) -> dict[str, Any]:
        token = self.token

        totp = self.totp

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "token": token,
            }
        )
        if totp is not UNSET:
            field_dict["totp"] = totp

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        token = d.pop("token")

        totp = d.pop("totp", UNSET)

        guest_session_body = cls(
            token=token,
            totp=totp,
        )

        return guest_session_body

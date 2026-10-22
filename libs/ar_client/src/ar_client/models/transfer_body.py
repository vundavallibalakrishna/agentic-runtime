from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from uuid import UUID


T = TypeVar("T", bound="TransferBody")


@_attrs_define
class TransferBody:
    """
    Attributes:
        new_owner_user_id (UUID):
    """

    new_owner_user_id: UUID

    def to_dict(self) -> dict[str, Any]:
        new_owner_user_id = str(self.new_owner_user_id)

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "newOwnerUserId": new_owner_user_id,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        new_owner_user_id = UUID(d.pop("newOwnerUserId"))

        transfer_body = cls(
            new_owner_user_id=new_owner_user_id,
        )

        return transfer_body

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from uuid import UUID






T = TypeVar("T", bound="ShareBody")



@_attrs_define
class ShareBody:
    """ 
        Attributes:
            principal_type (str):
            principal_id (UUID):
     """

    principal_type: str
    principal_id: UUID





    def to_dict(self) -> dict[str, Any]:
        principal_type = self.principal_type

        principal_id = str(self.principal_id)


        field_dict: dict[str, Any] = {}

        field_dict.update({
            "principalType": principal_type,
            "principalId": principal_id,
        })

        return field_dict



    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        principal_type = d.pop("principalType")

        principal_id = UUID(d.pop("principalId"))




        share_body = cls(
            principal_type=principal_type,
            principal_id=principal_id,
        )

        return share_body


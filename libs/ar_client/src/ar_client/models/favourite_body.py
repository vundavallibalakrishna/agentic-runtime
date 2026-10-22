from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from uuid import UUID


T = TypeVar("T", bound="FavouriteBody")


@_attrs_define
class FavouriteBody:
    """
    Attributes:
        agent_id (UUID):
        favourite (bool | Unset):  Default: True.
    """

    agent_id: UUID
    favourite: bool | Unset = True

    def to_dict(self) -> dict[str, Any]:
        agent_id = str(self.agent_id)

        favourite = self.favourite

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "agentId": agent_id,
            }
        )
        if favourite is not UNSET:
            field_dict["favourite"] = favourite

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        agent_id = UUID(d.pop("agentId"))

        favourite = d.pop("favourite", UNSET)

        favourite_body = cls(
            agent_id=agent_id,
            favourite=favourite,
        )

        return favourite_body

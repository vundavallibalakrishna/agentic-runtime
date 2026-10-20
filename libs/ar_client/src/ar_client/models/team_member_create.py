from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from uuid import UUID






T = TypeVar("T", bound="TeamMemberCreate")



@_attrs_define
class TeamMemberCreate:
    """ 
        Attributes:
            user_id (UUID):
            team_role (str | Unset):  Default: 'member'.
     """

    user_id: UUID
    team_role: str | Unset = 'member'





    def to_dict(self) -> dict[str, Any]:
        user_id = str(self.user_id)

        team_role = self.team_role


        field_dict: dict[str, Any] = {}

        field_dict.update({
            "userId": user_id,
        })
        if team_role is not UNSET:
            field_dict["teamRole"] = team_role

        return field_dict



    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        user_id = UUID(d.pop("userId"))




        team_role = d.pop("teamRole", UNSET)

        team_member_create = cls(
            user_id=user_id,
            team_role=team_role,
        )

        return team_member_create


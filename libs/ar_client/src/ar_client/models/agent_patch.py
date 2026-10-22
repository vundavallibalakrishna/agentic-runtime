from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast
from uuid import UUID


T = TypeVar("T", bound="AgentPatch")


@_attrs_define
class AgentPatch:
    """
    Attributes:
        name (None | str | Unset):
        description (None | str | Unset):
        visibility (None | str | Unset):
        owner_team_id (None | Unset | UUID):
        owner_user_id (None | Unset | UUID):
        risk_tier (None | str | Unset):
    """

    name: None | str | Unset = UNSET
    description: None | str | Unset = UNSET
    visibility: None | str | Unset = UNSET
    owner_team_id: None | Unset | UUID = UNSET
    owner_user_id: None | Unset | UUID = UNSET
    risk_tier: None | str | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        name: None | str | Unset
        if isinstance(self.name, Unset):
            name = UNSET
        else:
            name = self.name

        description: None | str | Unset
        if isinstance(self.description, Unset):
            description = UNSET
        else:
            description = self.description

        visibility: None | str | Unset
        if isinstance(self.visibility, Unset):
            visibility = UNSET
        else:
            visibility = self.visibility

        owner_team_id: None | str | Unset
        if isinstance(self.owner_team_id, Unset):
            owner_team_id = UNSET
        elif isinstance(self.owner_team_id, UUID):
            owner_team_id = str(self.owner_team_id)
        else:
            owner_team_id = self.owner_team_id

        owner_user_id: None | str | Unset
        if isinstance(self.owner_user_id, Unset):
            owner_user_id = UNSET
        elif isinstance(self.owner_user_id, UUID):
            owner_user_id = str(self.owner_user_id)
        else:
            owner_user_id = self.owner_user_id

        risk_tier: None | str | Unset
        if isinstance(self.risk_tier, Unset):
            risk_tier = UNSET
        else:
            risk_tier = self.risk_tier

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if name is not UNSET:
            field_dict["name"] = name
        if description is not UNSET:
            field_dict["description"] = description
        if visibility is not UNSET:
            field_dict["visibility"] = visibility
        if owner_team_id is not UNSET:
            field_dict["ownerTeamId"] = owner_team_id
        if owner_user_id is not UNSET:
            field_dict["ownerUserId"] = owner_user_id
        if risk_tier is not UNSET:
            field_dict["riskTier"] = risk_tier

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)

        def _parse_name(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        name = _parse_name(d.pop("name", UNSET))

        def _parse_description(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        description = _parse_description(d.pop("description", UNSET))

        def _parse_visibility(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        visibility = _parse_visibility(d.pop("visibility", UNSET))

        def _parse_owner_team_id(data: object) -> None | Unset | UUID:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                owner_team_id_type_0 = UUID(data)

                return owner_team_id_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(None | Unset | UUID, data)

        owner_team_id = _parse_owner_team_id(d.pop("ownerTeamId", UNSET))

        def _parse_owner_user_id(data: object) -> None | Unset | UUID:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                owner_user_id_type_0 = UUID(data)

                return owner_user_id_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(None | Unset | UUID, data)

        owner_user_id = _parse_owner_user_id(d.pop("ownerUserId", UNSET))

        def _parse_risk_tier(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        risk_tier = _parse_risk_tier(d.pop("riskTier", UNSET))

        agent_patch = cls(
            name=name,
            description=description,
            visibility=visibility,
            owner_team_id=owner_team_id,
            owner_user_id=owner_user_id,
            risk_tier=risk_tier,
        )

        return agent_patch

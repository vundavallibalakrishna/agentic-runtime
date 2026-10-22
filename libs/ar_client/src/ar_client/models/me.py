from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast
import datetime

if TYPE_CHECKING:
    from ..models.me_groups_item import MeGroupsItem
    from ..models.me_settings import MeSettings
    from ..models.me_teams_item import MeTeamsItem


T = TypeVar("T", bound="Me")


@_attrs_define
class Me:
    """Authenticated caller. Role and permission values stay catalogue tokens.

    Attributes:
        id (str):
        email (None | str | Unset):
        display_name (None | str | Unset):
        created_at (datetime.datetime | None | Unset):
        roles (list[str] | Unset):
        permissions (list[str] | Unset):
        teams (list[MeTeamsItem] | Unset):
        groups (list[MeGroupsItem] | Unset):
        settings (MeSettings | Unset):
    """

    id: str
    email: None | str | Unset = UNSET
    display_name: None | str | Unset = UNSET
    created_at: datetime.datetime | None | Unset = UNSET
    roles: list[str] | Unset = UNSET
    permissions: list[str] | Unset = UNSET
    teams: list[MeTeamsItem] | Unset = UNSET
    groups: list[MeGroupsItem] | Unset = UNSET
    settings: MeSettings | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        from ..models.me_groups_item import MeGroupsItem  # noqa: PLC0415
        from ..models.me_settings import MeSettings  # noqa: PLC0415
        from ..models.me_teams_item import MeTeamsItem  # noqa: PLC0415

        id = self.id

        email: None | str | Unset
        if isinstance(self.email, Unset):
            email = UNSET
        else:
            email = self.email

        display_name: None | str | Unset
        if isinstance(self.display_name, Unset):
            display_name = UNSET
        else:
            display_name = self.display_name

        created_at: None | str | Unset
        if isinstance(self.created_at, Unset):
            created_at = UNSET
        elif isinstance(self.created_at, datetime.datetime):
            created_at = self.created_at.isoformat()
        else:
            created_at = self.created_at

        roles: list[str] | Unset = UNSET
        if not isinstance(self.roles, Unset):
            roles = self.roles

        permissions: list[str] | Unset = UNSET
        if not isinstance(self.permissions, Unset):
            permissions = self.permissions

        teams: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.teams, Unset):
            teams = []
            for teams_item_data in self.teams:
                teams_item = teams_item_data.to_dict()
                teams.append(teams_item)

        groups: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.groups, Unset):
            groups = []
            for groups_item_data in self.groups:
                groups_item = groups_item_data.to_dict()
                groups.append(groups_item)

        settings: dict[str, Any] | Unset = UNSET
        if not isinstance(self.settings, Unset):
            settings = self.settings.to_dict()

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "id": id,
            }
        )
        if email is not UNSET:
            field_dict["email"] = email
        if display_name is not UNSET:
            field_dict["displayName"] = display_name
        if created_at is not UNSET:
            field_dict["createdAt"] = created_at
        if roles is not UNSET:
            field_dict["roles"] = roles
        if permissions is not UNSET:
            field_dict["permissions"] = permissions
        if teams is not UNSET:
            field_dict["teams"] = teams
        if groups is not UNSET:
            field_dict["groups"] = groups
        if settings is not UNSET:
            field_dict["settings"] = settings

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.me_groups_item import MeGroupsItem  # noqa: PLC0415
        from ..models.me_settings import MeSettings  # noqa: PLC0415
        from ..models.me_teams_item import MeTeamsItem  # noqa: PLC0415

        d = dict(src_dict)
        id = d.pop("id")

        def _parse_email(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        email = _parse_email(d.pop("email", UNSET))

        def _parse_display_name(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        display_name = _parse_display_name(d.pop("displayName", UNSET))

        def _parse_created_at(data: object) -> datetime.datetime | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                created_at_type_0 = datetime.datetime.fromisoformat(data)

                return created_at_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(datetime.datetime | None | Unset, data)

        created_at = _parse_created_at(d.pop("createdAt", UNSET))

        roles = cast(list[str], d.pop("roles", UNSET))

        permissions = cast(list[str], d.pop("permissions", UNSET))

        _teams = d.pop("teams", UNSET)
        teams: list[MeTeamsItem] | Unset = UNSET
        if _teams is not UNSET:
            teams = []
            for teams_item_data in _teams:
                teams_item = MeTeamsItem.from_dict(teams_item_data)

                teams.append(teams_item)

        _groups = d.pop("groups", UNSET)
        groups: list[MeGroupsItem] | Unset = UNSET
        if _groups is not UNSET:
            groups = []
            for groups_item_data in _groups:
                groups_item = MeGroupsItem.from_dict(groups_item_data)

                groups.append(groups_item)

        _settings = d.pop("settings", UNSET)
        settings: MeSettings | Unset
        if isinstance(_settings, Unset):
            settings = UNSET
        else:
            settings = MeSettings.from_dict(_settings)

        me = cls(
            id=id,
            email=email,
            display_name=display_name,
            created_at=created_at,
            roles=roles,
            permissions=permissions,
            teams=teams,
            groups=groups,
            settings=settings,
        )

        return me

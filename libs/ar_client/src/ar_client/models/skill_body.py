from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast
from uuid import UUID

if TYPE_CHECKING:
    from ..models.skill_asset import SkillAsset


T = TypeVar("T", bound="SkillBody")


@_attrs_define
class SkillBody:
    """
    Attributes:
        slug (str):
        name (str):
        description (str):
        visibility (str | Unset):  Default: 'tenant'.
        owner_team_id (None | Unset | UUID):
        instructions_md (str | Unset):  Default: ''.
        required_tools (list[str] | Unset):
        assets (list[SkillAsset] | Unset):
    """

    slug: str
    name: str
    description: str
    visibility: str | Unset = "tenant"
    owner_team_id: None | Unset | UUID = UNSET
    instructions_md: str | Unset = ""
    required_tools: list[str] | Unset = UNSET
    assets: list[SkillAsset] | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        from ..models.skill_asset import SkillAsset  # noqa: PLC0415

        slug = self.slug

        name = self.name

        description = self.description

        visibility = self.visibility

        owner_team_id: None | str | Unset
        if isinstance(self.owner_team_id, Unset):
            owner_team_id = UNSET
        elif isinstance(self.owner_team_id, UUID):
            owner_team_id = str(self.owner_team_id)
        else:
            owner_team_id = self.owner_team_id

        instructions_md = self.instructions_md

        required_tools: list[str] | Unset = UNSET
        if not isinstance(self.required_tools, Unset):
            required_tools = self.required_tools

        assets: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.assets, Unset):
            assets = []
            for assets_item_data in self.assets:
                assets_item = assets_item_data.to_dict()
                assets.append(assets_item)

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "slug": slug,
                "name": name,
                "description": description,
            }
        )
        if visibility is not UNSET:
            field_dict["visibility"] = visibility
        if owner_team_id is not UNSET:
            field_dict["ownerTeamId"] = owner_team_id
        if instructions_md is not UNSET:
            field_dict["instructionsMd"] = instructions_md
        if required_tools is not UNSET:
            field_dict["requiredTools"] = required_tools
        if assets is not UNSET:
            field_dict["assets"] = assets

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.skill_asset import SkillAsset  # noqa: PLC0415

        d = dict(src_dict)
        slug = d.pop("slug")

        name = d.pop("name")

        description = d.pop("description")

        visibility = d.pop("visibility", UNSET)

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

        instructions_md = d.pop("instructionsMd", UNSET)

        required_tools = cast(list[str], d.pop("requiredTools", UNSET))

        _assets = d.pop("assets", UNSET)
        assets: list[SkillAsset] | Unset = UNSET
        if _assets is not UNSET:
            assets = []
            for assets_item_data in _assets:
                assets_item = SkillAsset.from_dict(assets_item_data)

                assets.append(assets_item)

        skill_body = cls(
            slug=slug,
            name=name,
            description=description,
            visibility=visibility,
            owner_team_id=owner_team_id,
            instructions_md=instructions_md,
            required_tools=required_tools,
            assets=assets,
        )

        return skill_body

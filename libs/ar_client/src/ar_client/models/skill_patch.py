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


T = TypeVar("T", bound="SkillPatch")


@_attrs_define
class SkillPatch:
    """
    Attributes:
        name (None | str | Unset):
        description (None | str | Unset):
        visibility (None | str | Unset):
        owner_team_id (None | Unset | UUID):
        instructions_md (None | str | Unset):
        required_tools (list[str] | None | Unset):
        assets (list[SkillAsset] | None | Unset):
    """

    name: None | str | Unset = UNSET
    description: None | str | Unset = UNSET
    visibility: None | str | Unset = UNSET
    owner_team_id: None | Unset | UUID = UNSET
    instructions_md: None | str | Unset = UNSET
    required_tools: list[str] | None | Unset = UNSET
    assets: list[SkillAsset] | None | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        from ..models.skill_asset import SkillAsset  # noqa: PLC0415

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

        instructions_md: None | str | Unset
        if isinstance(self.instructions_md, Unset):
            instructions_md = UNSET
        else:
            instructions_md = self.instructions_md

        required_tools: list[str] | None | Unset
        if isinstance(self.required_tools, Unset):
            required_tools = UNSET
        elif isinstance(self.required_tools, list):
            required_tools = self.required_tools

        else:
            required_tools = self.required_tools

        assets: list[dict[str, Any]] | None | Unset
        if isinstance(self.assets, Unset):
            assets = UNSET
        elif isinstance(self.assets, list):
            assets = []
            for assets_type_0_item_data in self.assets:
                assets_type_0_item = assets_type_0_item_data.to_dict()
                assets.append(assets_type_0_item)

        else:
            assets = self.assets

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

        def _parse_instructions_md(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        instructions_md = _parse_instructions_md(d.pop("instructionsMd", UNSET))

        def _parse_required_tools(data: object) -> list[str] | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                required_tools_type_0 = cast(list[str], data)

                return required_tools_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(list[str] | None | Unset, data)

        required_tools = _parse_required_tools(d.pop("requiredTools", UNSET))

        def _parse_assets(data: object) -> list[SkillAsset] | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                assets_type_0 = []
                _assets_type_0 = data
                for assets_type_0_item_data in _assets_type_0:
                    assets_type_0_item = SkillAsset.from_dict(assets_type_0_item_data)

                    assets_type_0.append(assets_type_0_item)

                return assets_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(list[SkillAsset] | None | Unset, data)

        assets = _parse_assets(d.pop("assets", UNSET))

        skill_patch = cls(
            name=name,
            description=description,
            visibility=visibility,
            owner_team_id=owner_team_id,
            instructions_md=instructions_md,
            required_tools=required_tools,
            assets=assets,
        )

        return skill_patch

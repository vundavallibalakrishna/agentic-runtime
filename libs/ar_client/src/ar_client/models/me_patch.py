from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast

if TYPE_CHECKING:
  from ..models.me_patch_settings_type_0 import MePatchSettingsType0





T = TypeVar("T", bound="MePatch")



@_attrs_define
class MePatch:
    """ 
        Attributes:
            display_name (None | str | Unset):
            settings (MePatchSettingsType0 | None | Unset):
     """

    display_name: None | str | Unset = UNSET
    settings: MePatchSettingsType0 | None | Unset = UNSET





    def to_dict(self) -> dict[str, Any]:
        from ..models.me_patch_settings_type_0 import MePatchSettingsType0 # noqa: PLC0415
        display_name: None | str | Unset
        if isinstance(self.display_name, Unset):
            display_name = UNSET
        else:
            display_name = self.display_name

        settings: dict[str, Any] | None | Unset
        if isinstance(self.settings, Unset):
            settings = UNSET
        elif isinstance(self.settings, MePatchSettingsType0):
            settings = self.settings.to_dict()
        else:
            settings = self.settings


        field_dict: dict[str, Any] = {}

        field_dict.update({
        })
        if display_name is not UNSET:
            field_dict["displayName"] = display_name
        if settings is not UNSET:
            field_dict["settings"] = settings

        return field_dict



    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.me_patch_settings_type_0 import MePatchSettingsType0 # noqa: PLC0415
        d = dict(src_dict)
        def _parse_display_name(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        display_name = _parse_display_name(d.pop("displayName", UNSET))


        def _parse_settings(data: object) -> MePatchSettingsType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                settings_type_0 = MePatchSettingsType0.from_dict(data)



                return settings_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(MePatchSettingsType0 | None | Unset, data)

        settings = _parse_settings(d.pop("settings", UNSET))


        me_patch = cls(
            display_name=display_name,
            settings=settings,
        )

        return me_patch


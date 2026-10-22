from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast

if TYPE_CHECKING:
    from ..models.tenant_patch_settings_type_0 import TenantPatchSettingsType0


T = TypeVar("T", bound="TenantPatch")


@_attrs_define
class TenantPatch:
    """
    Attributes:
        name (None | str | Unset):
        settings (None | TenantPatchSettingsType0 | Unset):
    """

    name: None | str | Unset = UNSET
    settings: None | TenantPatchSettingsType0 | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        from ..models.tenant_patch_settings_type_0 import TenantPatchSettingsType0  # noqa: PLC0415

        name: None | str | Unset
        if isinstance(self.name, Unset):
            name = UNSET
        else:
            name = self.name

        settings: dict[str, Any] | None | Unset
        if isinstance(self.settings, Unset):
            settings = UNSET
        elif isinstance(self.settings, TenantPatchSettingsType0):
            settings = self.settings.to_dict()
        else:
            settings = self.settings

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if name is not UNSET:
            field_dict["name"] = name
        if settings is not UNSET:
            field_dict["settings"] = settings

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.tenant_patch_settings_type_0 import TenantPatchSettingsType0  # noqa: PLC0415

        d = dict(src_dict)

        def _parse_name(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        name = _parse_name(d.pop("name", UNSET))

        def _parse_settings(data: object) -> None | TenantPatchSettingsType0 | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                settings_type_0 = TenantPatchSettingsType0.from_dict(data)

                return settings_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(None | TenantPatchSettingsType0 | Unset, data)

        settings = _parse_settings(d.pop("settings", UNSET))

        tenant_patch = cls(
            name=name,
            settings=settings,
        )

        return tenant_patch

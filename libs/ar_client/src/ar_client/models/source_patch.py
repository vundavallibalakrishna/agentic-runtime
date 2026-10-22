from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast

if TYPE_CHECKING:
    from ..models.source_patch_config_type_0 import SourcePatchConfigType0


T = TypeVar("T", bound="SourcePatch")


@_attrs_define
class SourcePatch:
    """
    Attributes:
        name (None | str | Unset):
        config (None | SourcePatchConfigType0 | Unset):
        sync_schedule (None | str | Unset):
    """

    name: None | str | Unset = UNSET
    config: None | SourcePatchConfigType0 | Unset = UNSET
    sync_schedule: None | str | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        from ..models.source_patch_config_type_0 import SourcePatchConfigType0  # noqa: PLC0415

        name: None | str | Unset
        if isinstance(self.name, Unset):
            name = UNSET
        else:
            name = self.name

        config: dict[str, Any] | None | Unset
        if isinstance(self.config, Unset):
            config = UNSET
        elif isinstance(self.config, SourcePatchConfigType0):
            config = self.config.to_dict()
        else:
            config = self.config

        sync_schedule: None | str | Unset
        if isinstance(self.sync_schedule, Unset):
            sync_schedule = UNSET
        else:
            sync_schedule = self.sync_schedule

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if name is not UNSET:
            field_dict["name"] = name
        if config is not UNSET:
            field_dict["config"] = config
        if sync_schedule is not UNSET:
            field_dict["syncSchedule"] = sync_schedule

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.source_patch_config_type_0 import SourcePatchConfigType0  # noqa: PLC0415

        d = dict(src_dict)

        def _parse_name(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        name = _parse_name(d.pop("name", UNSET))

        def _parse_config(data: object) -> None | SourcePatchConfigType0 | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                config_type_0 = SourcePatchConfigType0.from_dict(data)

                return config_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(None | SourcePatchConfigType0 | Unset, data)

        config = _parse_config(d.pop("config", UNSET))

        def _parse_sync_schedule(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        sync_schedule = _parse_sync_schedule(d.pop("syncSchedule", UNSET))

        source_patch = cls(
            name=name,
            config=config,
            sync_schedule=sync_schedule,
        )

        return source_patch

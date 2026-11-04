from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast

if TYPE_CHECKING:
    from ..models.connector_install_patch_config_type_0 import ConnectorInstallPatchConfigType0


T = TypeVar("T", bound="ConnectorInstallPatch")


@_attrs_define
class ConnectorInstallPatch:
    """
    Attributes:
        connection_name (None | str | Unset):
        status (None | str | Unset):
        disabled_tools (list[str] | None | Unset):
        config (ConnectorInstallPatchConfigType0 | None | Unset):
    """

    connection_name: None | str | Unset = UNSET
    status: None | str | Unset = UNSET
    disabled_tools: list[str] | None | Unset = UNSET
    config: ConnectorInstallPatchConfigType0 | None | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        from ..models.connector_install_patch_config_type_0 import ConnectorInstallPatchConfigType0  # noqa: PLC0415

        connection_name: None | str | Unset
        if isinstance(self.connection_name, Unset):
            connection_name = UNSET
        else:
            connection_name = self.connection_name

        status: None | str | Unset
        if isinstance(self.status, Unset):
            status = UNSET
        else:
            status = self.status

        disabled_tools: list[str] | None | Unset
        if isinstance(self.disabled_tools, Unset):
            disabled_tools = UNSET
        elif isinstance(self.disabled_tools, list):
            disabled_tools = self.disabled_tools

        else:
            disabled_tools = self.disabled_tools

        config: dict[str, Any] | None | Unset
        if isinstance(self.config, Unset):
            config = UNSET
        elif isinstance(self.config, ConnectorInstallPatchConfigType0):
            config = self.config.to_dict()
        else:
            config = self.config

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if connection_name is not UNSET:
            field_dict["connectionName"] = connection_name
        if status is not UNSET:
            field_dict["status"] = status
        if disabled_tools is not UNSET:
            field_dict["disabledTools"] = disabled_tools
        if config is not UNSET:
            field_dict["config"] = config

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.connector_install_patch_config_type_0 import ConnectorInstallPatchConfigType0  # noqa: PLC0415

        d = dict(src_dict)

        def _parse_connection_name(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        connection_name = _parse_connection_name(d.pop("connectionName", UNSET))

        def _parse_status(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        status = _parse_status(d.pop("status", UNSET))

        def _parse_disabled_tools(data: object) -> list[str] | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                disabled_tools_type_0 = cast(list[str], data)

                return disabled_tools_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(list[str] | None | Unset, data)

        disabled_tools = _parse_disabled_tools(d.pop("disabledTools", UNSET))

        def _parse_config(data: object) -> ConnectorInstallPatchConfigType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                config_type_0 = ConnectorInstallPatchConfigType0.from_dict(data)

                return config_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(ConnectorInstallPatchConfigType0 | None | Unset, data)

        config = _parse_config(d.pop("config", UNSET))

        connector_install_patch = cls(
            connection_name=connection_name,
            status=status,
            disabled_tools=disabled_tools,
            config=config,
        )

        return connector_install_patch

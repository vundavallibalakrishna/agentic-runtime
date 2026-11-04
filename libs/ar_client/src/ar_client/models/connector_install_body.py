from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast

if TYPE_CHECKING:
    from ..models.connector_install_body_config_type_0 import ConnectorInstallBodyConfigType0


T = TypeVar("T", bound="ConnectorInstallBody")


@_attrs_define
class ConnectorInstallBody:
    """
    Attributes:
        connection_name (str | Unset):  Default: ''.
        name (str | Unset):  Default: ''.
        kind (str | Unset):  Default: ''.
        secret (str | Unset):  Default: ''.
        username (str | Unset):  Default: ''.
        client_id (str | Unset):  Default: ''.
        config (ConnectorInstallBodyConfigType0 | None | Unset):
    """

    connection_name: str | Unset = ""
    name: str | Unset = ""
    kind: str | Unset = ""
    secret: str | Unset = ""
    username: str | Unset = ""
    client_id: str | Unset = ""
    config: ConnectorInstallBodyConfigType0 | None | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        from ..models.connector_install_body_config_type_0 import ConnectorInstallBodyConfigType0  # noqa: PLC0415

        connection_name = self.connection_name

        name = self.name

        kind = self.kind

        secret = self.secret

        username = self.username

        client_id = self.client_id

        config: dict[str, Any] | None | Unset
        if isinstance(self.config, Unset):
            config = UNSET
        elif isinstance(self.config, ConnectorInstallBodyConfigType0):
            config = self.config.to_dict()
        else:
            config = self.config

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if connection_name is not UNSET:
            field_dict["connectionName"] = connection_name
        if name is not UNSET:
            field_dict["name"] = name
        if kind is not UNSET:
            field_dict["kind"] = kind
        if secret is not UNSET:
            field_dict["secret"] = secret
        if username is not UNSET:
            field_dict["username"] = username
        if client_id is not UNSET:
            field_dict["clientId"] = client_id
        if config is not UNSET:
            field_dict["config"] = config

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.connector_install_body_config_type_0 import ConnectorInstallBodyConfigType0  # noqa: PLC0415

        d = dict(src_dict)
        connection_name = d.pop("connectionName", UNSET)

        name = d.pop("name", UNSET)

        kind = d.pop("kind", UNSET)

        secret = d.pop("secret", UNSET)

        username = d.pop("username", UNSET)

        client_id = d.pop("clientId", UNSET)

        def _parse_config(data: object) -> ConnectorInstallBodyConfigType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                config_type_0 = ConnectorInstallBodyConfigType0.from_dict(data)

                return config_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(ConnectorInstallBodyConfigType0 | None | Unset, data)

        config = _parse_config(d.pop("config", UNSET))

        connector_install_body = cls(
            connection_name=connection_name,
            name=name,
            kind=kind,
            secret=secret,
            username=username,
            client_id=client_id,
            config=config,
        )

        return connector_install_body

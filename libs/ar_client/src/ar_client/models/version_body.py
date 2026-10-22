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
    from ..models.version_body_config_type_0 import VersionBodyConfigType0


T = TypeVar("T", bound="VersionBody")


@_attrs_define
class VersionBody:
    """
    Attributes:
        version (str | Unset):  Default: '1.0.0'.
        endpoint_url (None | str | Unset):
        auth_mode (None | str | Unset):
        config (None | Unset | VersionBodyConfigType0):
        secret_id (None | Unset | UUID):
        credential_provider_id (None | Unset | UUID):
    """

    version: str | Unset = "1.0.0"
    endpoint_url: None | str | Unset = UNSET
    auth_mode: None | str | Unset = UNSET
    config: None | Unset | VersionBodyConfigType0 = UNSET
    secret_id: None | Unset | UUID = UNSET
    credential_provider_id: None | Unset | UUID = UNSET

    def to_dict(self) -> dict[str, Any]:
        from ..models.version_body_config_type_0 import VersionBodyConfigType0  # noqa: PLC0415

        version = self.version

        endpoint_url: None | str | Unset
        if isinstance(self.endpoint_url, Unset):
            endpoint_url = UNSET
        else:
            endpoint_url = self.endpoint_url

        auth_mode: None | str | Unset
        if isinstance(self.auth_mode, Unset):
            auth_mode = UNSET
        else:
            auth_mode = self.auth_mode

        config: dict[str, Any] | None | Unset
        if isinstance(self.config, Unset):
            config = UNSET
        elif isinstance(self.config, VersionBodyConfigType0):
            config = self.config.to_dict()
        else:
            config = self.config

        secret_id: None | str | Unset
        if isinstance(self.secret_id, Unset):
            secret_id = UNSET
        elif isinstance(self.secret_id, UUID):
            secret_id = str(self.secret_id)
        else:
            secret_id = self.secret_id

        credential_provider_id: None | str | Unset
        if isinstance(self.credential_provider_id, Unset):
            credential_provider_id = UNSET
        elif isinstance(self.credential_provider_id, UUID):
            credential_provider_id = str(self.credential_provider_id)
        else:
            credential_provider_id = self.credential_provider_id

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if version is not UNSET:
            field_dict["version"] = version
        if endpoint_url is not UNSET:
            field_dict["endpointUrl"] = endpoint_url
        if auth_mode is not UNSET:
            field_dict["authMode"] = auth_mode
        if config is not UNSET:
            field_dict["config"] = config
        if secret_id is not UNSET:
            field_dict["secretId"] = secret_id
        if credential_provider_id is not UNSET:
            field_dict["credentialProviderId"] = credential_provider_id

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.version_body_config_type_0 import VersionBodyConfigType0  # noqa: PLC0415

        d = dict(src_dict)
        version = d.pop("version", UNSET)

        def _parse_endpoint_url(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        endpoint_url = _parse_endpoint_url(d.pop("endpointUrl", UNSET))

        def _parse_auth_mode(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        auth_mode = _parse_auth_mode(d.pop("authMode", UNSET))

        def _parse_config(data: object) -> None | Unset | VersionBodyConfigType0:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                config_type_0 = VersionBodyConfigType0.from_dict(data)

                return config_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(None | Unset | VersionBodyConfigType0, data)

        config = _parse_config(d.pop("config", UNSET))

        def _parse_secret_id(data: object) -> None | Unset | UUID:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                secret_id_type_0 = UUID(data)

                return secret_id_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(None | Unset | UUID, data)

        secret_id = _parse_secret_id(d.pop("secretId", UNSET))

        def _parse_credential_provider_id(data: object) -> None | Unset | UUID:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                credential_provider_id_type_0 = UUID(data)

                return credential_provider_id_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(None | Unset | UUID, data)

        credential_provider_id = _parse_credential_provider_id(d.pop("credentialProviderId", UNSET))

        version_body = cls(
            version=version,
            endpoint_url=endpoint_url,
            auth_mode=auth_mode,
            config=config,
            secret_id=secret_id,
            credential_provider_id=credential_provider_id,
        )

        return version_body

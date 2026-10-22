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
    from ..models.source_body_config_type_0 import SourceBodyConfigType0


T = TypeVar("T", bound="SourceBody")


@_attrs_define
class SourceBody:
    """
    Attributes:
        name (str | Unset):  Default: ''.
        kind (str | Unset):  Default: ''.
        config (None | SourceBodyConfigType0 | Unset):
        secret_id (None | Unset | UUID):
        data_connection_id (None | Unset | UUID):
        sync_schedule (None | str | Unset):
        acl_sync_schedule (None | str | Unset):
    """

    name: str | Unset = ""
    kind: str | Unset = ""
    config: None | SourceBodyConfigType0 | Unset = UNSET
    secret_id: None | Unset | UUID = UNSET
    data_connection_id: None | Unset | UUID = UNSET
    sync_schedule: None | str | Unset = UNSET
    acl_sync_schedule: None | str | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        from ..models.source_body_config_type_0 import SourceBodyConfigType0  # noqa: PLC0415

        name = self.name

        kind = self.kind

        config: dict[str, Any] | None | Unset
        if isinstance(self.config, Unset):
            config = UNSET
        elif isinstance(self.config, SourceBodyConfigType0):
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

        data_connection_id: None | str | Unset
        if isinstance(self.data_connection_id, Unset):
            data_connection_id = UNSET
        elif isinstance(self.data_connection_id, UUID):
            data_connection_id = str(self.data_connection_id)
        else:
            data_connection_id = self.data_connection_id

        sync_schedule: None | str | Unset
        if isinstance(self.sync_schedule, Unset):
            sync_schedule = UNSET
        else:
            sync_schedule = self.sync_schedule

        acl_sync_schedule: None | str | Unset
        if isinstance(self.acl_sync_schedule, Unset):
            acl_sync_schedule = UNSET
        else:
            acl_sync_schedule = self.acl_sync_schedule

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if name is not UNSET:
            field_dict["name"] = name
        if kind is not UNSET:
            field_dict["kind"] = kind
        if config is not UNSET:
            field_dict["config"] = config
        if secret_id is not UNSET:
            field_dict["secretId"] = secret_id
        if data_connection_id is not UNSET:
            field_dict["dataConnectionId"] = data_connection_id
        if sync_schedule is not UNSET:
            field_dict["syncSchedule"] = sync_schedule
        if acl_sync_schedule is not UNSET:
            field_dict["aclSyncSchedule"] = acl_sync_schedule

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.source_body_config_type_0 import SourceBodyConfigType0  # noqa: PLC0415

        d = dict(src_dict)
        name = d.pop("name", UNSET)

        kind = d.pop("kind", UNSET)

        def _parse_config(data: object) -> None | SourceBodyConfigType0 | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                config_type_0 = SourceBodyConfigType0.from_dict(data)

                return config_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(None | SourceBodyConfigType0 | Unset, data)

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

        def _parse_data_connection_id(data: object) -> None | Unset | UUID:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                data_connection_id_type_0 = UUID(data)

                return data_connection_id_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(None | Unset | UUID, data)

        data_connection_id = _parse_data_connection_id(d.pop("dataConnectionId", UNSET))

        def _parse_sync_schedule(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        sync_schedule = _parse_sync_schedule(d.pop("syncSchedule", UNSET))

        def _parse_acl_sync_schedule(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        acl_sync_schedule = _parse_acl_sync_schedule(d.pop("aclSyncSchedule", UNSET))

        source_body = cls(
            name=name,
            kind=kind,
            config=config,
            secret_id=secret_id,
            data_connection_id=data_connection_id,
            sync_schedule=sync_schedule,
            acl_sync_schedule=acl_sync_schedule,
        )

        return source_body

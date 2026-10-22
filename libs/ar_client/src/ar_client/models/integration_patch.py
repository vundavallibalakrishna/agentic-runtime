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
    from ..models.credentials_body import CredentialsBody
    from ..models.integration_patch_agent_routing_type_0_item import (
        IntegrationPatchAgentRoutingType0Item,
    )
    from ..models.integration_patch_config_type_0 import IntegrationPatchConfigType0


T = TypeVar("T", bound="IntegrationPatch")


@_attrs_define
class IntegrationPatch:
    """
    Attributes:
        name (None | str | Unset):
        config (IntegrationPatchConfigType0 | None | Unset):
        credentials (CredentialsBody | None | Unset):
        default_agent_id (None | Unset | UUID):
        agent_routing (list[IntegrationPatchAgentRoutingType0Item] | None | Unset):
        status (None | str | Unset):
    """

    name: None | str | Unset = UNSET
    config: IntegrationPatchConfigType0 | None | Unset = UNSET
    credentials: CredentialsBody | None | Unset = UNSET
    default_agent_id: None | Unset | UUID = UNSET
    agent_routing: list[IntegrationPatchAgentRoutingType0Item] | None | Unset = UNSET
    status: None | str | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        from ..models.credentials_body import CredentialsBody  # noqa: PLC0415
        from ..models.integration_patch_agent_routing_type_0_item import (
            IntegrationPatchAgentRoutingType0Item,
        )  # noqa: PLC0415
        from ..models.integration_patch_config_type_0 import IntegrationPatchConfigType0  # noqa: PLC0415

        name: None | str | Unset
        if isinstance(self.name, Unset):
            name = UNSET
        else:
            name = self.name

        config: dict[str, Any] | None | Unset
        if isinstance(self.config, Unset):
            config = UNSET
        elif isinstance(self.config, IntegrationPatchConfigType0):
            config = self.config.to_dict()
        else:
            config = self.config

        credentials: dict[str, Any] | None | Unset
        if isinstance(self.credentials, Unset):
            credentials = UNSET
        elif isinstance(self.credentials, CredentialsBody):
            credentials = self.credentials.to_dict()
        else:
            credentials = self.credentials

        default_agent_id: None | str | Unset
        if isinstance(self.default_agent_id, Unset):
            default_agent_id = UNSET
        elif isinstance(self.default_agent_id, UUID):
            default_agent_id = str(self.default_agent_id)
        else:
            default_agent_id = self.default_agent_id

        agent_routing: list[dict[str, Any]] | None | Unset
        if isinstance(self.agent_routing, Unset):
            agent_routing = UNSET
        elif isinstance(self.agent_routing, list):
            agent_routing = []
            for agent_routing_type_0_item_data in self.agent_routing:
                agent_routing_type_0_item = agent_routing_type_0_item_data.to_dict()
                agent_routing.append(agent_routing_type_0_item)

        else:
            agent_routing = self.agent_routing

        status: None | str | Unset
        if isinstance(self.status, Unset):
            status = UNSET
        else:
            status = self.status

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if name is not UNSET:
            field_dict["name"] = name
        if config is not UNSET:
            field_dict["config"] = config
        if credentials is not UNSET:
            field_dict["credentials"] = credentials
        if default_agent_id is not UNSET:
            field_dict["defaultAgentId"] = default_agent_id
        if agent_routing is not UNSET:
            field_dict["agentRouting"] = agent_routing
        if status is not UNSET:
            field_dict["status"] = status

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.credentials_body import CredentialsBody  # noqa: PLC0415
        from ..models.integration_patch_agent_routing_type_0_item import (
            IntegrationPatchAgentRoutingType0Item,
        )  # noqa: PLC0415
        from ..models.integration_patch_config_type_0 import IntegrationPatchConfigType0  # noqa: PLC0415

        d = dict(src_dict)

        def _parse_name(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        name = _parse_name(d.pop("name", UNSET))

        def _parse_config(data: object) -> IntegrationPatchConfigType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                config_type_0 = IntegrationPatchConfigType0.from_dict(data)

                return config_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(IntegrationPatchConfigType0 | None | Unset, data)

        config = _parse_config(d.pop("config", UNSET))

        def _parse_credentials(data: object) -> CredentialsBody | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                credentials_type_0 = CredentialsBody.from_dict(data)

                return credentials_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(CredentialsBody | None | Unset, data)

        credentials = _parse_credentials(d.pop("credentials", UNSET))

        def _parse_default_agent_id(data: object) -> None | Unset | UUID:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                default_agent_id_type_0 = UUID(data)

                return default_agent_id_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(None | Unset | UUID, data)

        default_agent_id = _parse_default_agent_id(d.pop("defaultAgentId", UNSET))

        def _parse_agent_routing(
            data: object,
        ) -> list[IntegrationPatchAgentRoutingType0Item] | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                agent_routing_type_0 = []
                _agent_routing_type_0 = data
                for agent_routing_type_0_item_data in _agent_routing_type_0:
                    agent_routing_type_0_item = IntegrationPatchAgentRoutingType0Item.from_dict(
                        agent_routing_type_0_item_data
                    )

                    agent_routing_type_0.append(agent_routing_type_0_item)

                return agent_routing_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(list[IntegrationPatchAgentRoutingType0Item] | None | Unset, data)

        agent_routing = _parse_agent_routing(d.pop("agentRouting", UNSET))

        def _parse_status(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        status = _parse_status(d.pop("status", UNSET))

        integration_patch = cls(
            name=name,
            config=config,
            credentials=credentials,
            default_agent_id=default_agent_id,
            agent_routing=agent_routing,
            status=status,
        )

        return integration_patch

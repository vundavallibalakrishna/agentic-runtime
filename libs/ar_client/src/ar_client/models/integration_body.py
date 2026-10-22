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
    from ..models.integration_body_agent_routing_item import IntegrationBodyAgentRoutingItem
    from ..models.integration_body_config import IntegrationBodyConfig


T = TypeVar("T", bound="IntegrationBody")


@_attrs_define
class IntegrationBody:
    """
    Attributes:
        kind (str):
        name (str):
        config (IntegrationBodyConfig | Unset):
        credentials (CredentialsBody | None | Unset):
        default_agent_id (None | Unset | UUID):
        agent_routing (list[IntegrationBodyAgentRoutingItem] | Unset):
    """

    kind: str
    name: str
    config: IntegrationBodyConfig | Unset = UNSET
    credentials: CredentialsBody | None | Unset = UNSET
    default_agent_id: None | Unset | UUID = UNSET
    agent_routing: list[IntegrationBodyAgentRoutingItem] | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        from ..models.credentials_body import CredentialsBody  # noqa: PLC0415
        from ..models.integration_body_agent_routing_item import IntegrationBodyAgentRoutingItem  # noqa: PLC0415
        from ..models.integration_body_config import IntegrationBodyConfig  # noqa: PLC0415

        kind = self.kind

        name = self.name

        config: dict[str, Any] | Unset = UNSET
        if not isinstance(self.config, Unset):
            config = self.config.to_dict()

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

        agent_routing: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.agent_routing, Unset):
            agent_routing = []
            for agent_routing_item_data in self.agent_routing:
                agent_routing_item = agent_routing_item_data.to_dict()
                agent_routing.append(agent_routing_item)

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "kind": kind,
                "name": name,
            }
        )
        if config is not UNSET:
            field_dict["config"] = config
        if credentials is not UNSET:
            field_dict["credentials"] = credentials
        if default_agent_id is not UNSET:
            field_dict["defaultAgentId"] = default_agent_id
        if agent_routing is not UNSET:
            field_dict["agentRouting"] = agent_routing

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.credentials_body import CredentialsBody  # noqa: PLC0415
        from ..models.integration_body_agent_routing_item import IntegrationBodyAgentRoutingItem  # noqa: PLC0415
        from ..models.integration_body_config import IntegrationBodyConfig  # noqa: PLC0415

        d = dict(src_dict)
        kind = d.pop("kind")

        name = d.pop("name")

        _config = d.pop("config", UNSET)
        config: IntegrationBodyConfig | Unset
        if isinstance(_config, Unset):
            config = UNSET
        else:
            config = IntegrationBodyConfig.from_dict(_config)

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

        _agent_routing = d.pop("agentRouting", UNSET)
        agent_routing: list[IntegrationBodyAgentRoutingItem] | Unset = UNSET
        if _agent_routing is not UNSET:
            agent_routing = []
            for agent_routing_item_data in _agent_routing:
                agent_routing_item = IntegrationBodyAgentRoutingItem.from_dict(
                    agent_routing_item_data
                )

                agent_routing.append(agent_routing_item)

        integration_body = cls(
            kind=kind,
            name=name,
            config=config,
            credentials=credentials,
            default_agent_id=default_agent_id,
            agent_routing=agent_routing,
        )

        return integration_body

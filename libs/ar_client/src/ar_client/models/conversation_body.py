from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast
from uuid import UUID


T = TypeVar("T", bound="ConversationBody")


@_attrs_define
class ConversationBody:
    """
    Attributes:
        agent_id (None | Unset | UUID):
        agent_version_id (None | Unset | UUID):
        model_alias (None | str | Unset):
    """

    agent_id: None | Unset | UUID = UNSET
    agent_version_id: None | Unset | UUID = UNSET
    model_alias: None | str | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        agent_id: None | str | Unset
        if isinstance(self.agent_id, Unset):
            agent_id = UNSET
        elif isinstance(self.agent_id, UUID):
            agent_id = str(self.agent_id)
        else:
            agent_id = self.agent_id

        agent_version_id: None | str | Unset
        if isinstance(self.agent_version_id, Unset):
            agent_version_id = UNSET
        elif isinstance(self.agent_version_id, UUID):
            agent_version_id = str(self.agent_version_id)
        else:
            agent_version_id = self.agent_version_id

        model_alias: None | str | Unset
        if isinstance(self.model_alias, Unset):
            model_alias = UNSET
        else:
            model_alias = self.model_alias

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if agent_id is not UNSET:
            field_dict["agentId"] = agent_id
        if agent_version_id is not UNSET:
            field_dict["agentVersionId"] = agent_version_id
        if model_alias is not UNSET:
            field_dict["modelAlias"] = model_alias

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)

        def _parse_agent_id(data: object) -> None | Unset | UUID:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                agent_id_type_0 = UUID(data)

                return agent_id_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(None | Unset | UUID, data)

        agent_id = _parse_agent_id(d.pop("agentId", UNSET))

        def _parse_agent_version_id(data: object) -> None | Unset | UUID:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                agent_version_id_type_0 = UUID(data)

                return agent_version_id_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(None | Unset | UUID, data)

        agent_version_id = _parse_agent_version_id(d.pop("agentVersionId", UNSET))

        def _parse_model_alias(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        model_alias = _parse_model_alias(d.pop("modelAlias", UNSET))

        conversation_body = cls(
            agent_id=agent_id,
            agent_version_id=agent_version_id,
            model_alias=model_alias,
        )

        return conversation_body

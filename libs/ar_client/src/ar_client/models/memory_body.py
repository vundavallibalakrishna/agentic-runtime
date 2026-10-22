from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast
from uuid import UUID


T = TypeVar("T", bound="MemoryBody")


@_attrs_define
class MemoryBody:
    """
    Attributes:
        content (str):
        scope (str | Unset):  Default: 'user'.
        agent_id (None | Unset | UUID):
        category (None | str | Unset):
    """

    content: str
    scope: str | Unset = "user"
    agent_id: None | Unset | UUID = UNSET
    category: None | str | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        content = self.content

        scope = self.scope

        agent_id: None | str | Unset
        if isinstance(self.agent_id, Unset):
            agent_id = UNSET
        elif isinstance(self.agent_id, UUID):
            agent_id = str(self.agent_id)
        else:
            agent_id = self.agent_id

        category: None | str | Unset
        if isinstance(self.category, Unset):
            category = UNSET
        else:
            category = self.category

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "content": content,
            }
        )
        if scope is not UNSET:
            field_dict["scope"] = scope
        if agent_id is not UNSET:
            field_dict["agentId"] = agent_id
        if category is not UNSET:
            field_dict["category"] = category

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        content = d.pop("content")

        scope = d.pop("scope", UNSET)

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

        def _parse_category(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        category = _parse_category(d.pop("category", UNSET))

        memory_body = cls(
            content=content,
            scope=scope,
            agent_id=agent_id,
            category=category,
        )

        return memory_body

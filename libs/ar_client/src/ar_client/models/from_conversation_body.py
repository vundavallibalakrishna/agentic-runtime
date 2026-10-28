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
    from ..models.from_conversation_body_assertions_type_0_item import (
        FromConversationBodyAssertionsType0Item,
    )


T = TypeVar("T", bound="FromConversationBody")


@_attrs_define
class FromConversationBody:
    """
    Attributes:
        conversation_id (UUID):
        message_id (UUID):
        assertions (list[FromConversationBodyAssertionsType0Item] | None | Unset):
        name (None | str | Unset):
        tags (list[str] | None | Unset):
    """

    conversation_id: UUID
    message_id: UUID
    assertions: list[FromConversationBodyAssertionsType0Item] | None | Unset = UNSET
    name: None | str | Unset = UNSET
    tags: list[str] | None | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        from ..models.from_conversation_body_assertions_type_0_item import (
            FromConversationBodyAssertionsType0Item,
        )  # noqa: PLC0415

        conversation_id = str(self.conversation_id)

        message_id = str(self.message_id)

        assertions: list[dict[str, Any]] | None | Unset
        if isinstance(self.assertions, Unset):
            assertions = UNSET
        elif isinstance(self.assertions, list):
            assertions = []
            for assertions_type_0_item_data in self.assertions:
                assertions_type_0_item = assertions_type_0_item_data.to_dict()
                assertions.append(assertions_type_0_item)

        else:
            assertions = self.assertions

        name: None | str | Unset
        if isinstance(self.name, Unset):
            name = UNSET
        else:
            name = self.name

        tags: list[str] | None | Unset
        if isinstance(self.tags, Unset):
            tags = UNSET
        elif isinstance(self.tags, list):
            tags = self.tags

        else:
            tags = self.tags

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "conversationId": conversation_id,
                "messageId": message_id,
            }
        )
        if assertions is not UNSET:
            field_dict["assertions"] = assertions
        if name is not UNSET:
            field_dict["name"] = name
        if tags is not UNSET:
            field_dict["tags"] = tags

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.from_conversation_body_assertions_type_0_item import (
            FromConversationBodyAssertionsType0Item,
        )  # noqa: PLC0415

        d = dict(src_dict)
        conversation_id = UUID(d.pop("conversationId"))

        message_id = UUID(d.pop("messageId"))

        def _parse_assertions(
            data: object,
        ) -> list[FromConversationBodyAssertionsType0Item] | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                assertions_type_0 = []
                _assertions_type_0 = data
                for assertions_type_0_item_data in _assertions_type_0:
                    assertions_type_0_item = FromConversationBodyAssertionsType0Item.from_dict(
                        assertions_type_0_item_data
                    )

                    assertions_type_0.append(assertions_type_0_item)

                return assertions_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(list[FromConversationBodyAssertionsType0Item] | None | Unset, data)

        assertions = _parse_assertions(d.pop("assertions", UNSET))

        def _parse_name(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        name = _parse_name(d.pop("name", UNSET))

        def _parse_tags(data: object) -> list[str] | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                tags_type_0 = cast(list[str], data)

                return tags_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(list[str] | None | Unset, data)

        tags = _parse_tags(d.pop("tags", UNSET))

        from_conversation_body = cls(
            conversation_id=conversation_id,
            message_id=message_id,
            assertions=assertions,
            name=name,
            tags=tags,
        )

        return from_conversation_body

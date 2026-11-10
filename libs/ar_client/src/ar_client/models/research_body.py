from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast
from uuid import UUID


T = TypeVar("T", bound="ResearchBody")


@_attrs_define
class ResearchBody:
    """
    Attributes:
        question (str):
        conversation_id (None | Unset | UUID):
        max_depth (int | Unset):  Default: 2.
        max_breadth (int | Unset):  Default: 4.
        max_wall_clock_s (int | Unset):  Default: 120.
        max_cost_micros (int | Unset):  Default: 1000000.
    """

    question: str
    conversation_id: None | Unset | UUID = UNSET
    max_depth: int | Unset = 2
    max_breadth: int | Unset = 4
    max_wall_clock_s: int | Unset = 120
    max_cost_micros: int | Unset = 1000000

    def to_dict(self) -> dict[str, Any]:
        question = self.question

        conversation_id: None | str | Unset
        if isinstance(self.conversation_id, Unset):
            conversation_id = UNSET
        elif isinstance(self.conversation_id, UUID):
            conversation_id = str(self.conversation_id)
        else:
            conversation_id = self.conversation_id

        max_depth = self.max_depth

        max_breadth = self.max_breadth

        max_wall_clock_s = self.max_wall_clock_s

        max_cost_micros = self.max_cost_micros

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "question": question,
            }
        )
        if conversation_id is not UNSET:
            field_dict["conversationId"] = conversation_id
        if max_depth is not UNSET:
            field_dict["maxDepth"] = max_depth
        if max_breadth is not UNSET:
            field_dict["maxBreadth"] = max_breadth
        if max_wall_clock_s is not UNSET:
            field_dict["maxWallClockS"] = max_wall_clock_s
        if max_cost_micros is not UNSET:
            field_dict["maxCostMicros"] = max_cost_micros

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        question = d.pop("question")

        def _parse_conversation_id(data: object) -> None | Unset | UUID:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                conversation_id_type_0 = UUID(data)

                return conversation_id_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(None | Unset | UUID, data)

        conversation_id = _parse_conversation_id(d.pop("conversationId", UNSET))

        max_depth = d.pop("maxDepth", UNSET)

        max_breadth = d.pop("maxBreadth", UNSET)

        max_wall_clock_s = d.pop("maxWallClockS", UNSET)

        max_cost_micros = d.pop("maxCostMicros", UNSET)

        research_body = cls(
            question=question,
            conversation_id=conversation_id,
            max_depth=max_depth,
            max_breadth=max_breadth,
            max_wall_clock_s=max_wall_clock_s,
            max_cost_micros=max_cost_micros,
        )

        return research_body

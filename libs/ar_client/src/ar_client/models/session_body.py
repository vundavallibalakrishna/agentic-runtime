from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define

T = TypeVar("T", bound="SessionBody")


@_attrs_define
class SessionBody:
    """
    Attributes:
        instruction (str):
    """

    instruction: str

    def to_dict(self) -> dict[str, Any]:
        instruction = self.instruction

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "instruction": instruction,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        instruction = d.pop("instruction")

        session_body = cls(
            instruction=instruction,
        )

        return session_body

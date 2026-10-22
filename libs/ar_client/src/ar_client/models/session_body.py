from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset


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

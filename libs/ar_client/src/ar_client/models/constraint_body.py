from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset


T = TypeVar("T", bound="ConstraintBody")


@_attrs_define
class ConstraintBody:
    """
    Attributes:
        role_a (str):
        role_b (str):
        applies_to (str):
    """

    role_a: str
    role_b: str
    applies_to: str

    def to_dict(self) -> dict[str, Any]:
        role_a = self.role_a

        role_b = self.role_b

        applies_to = self.applies_to

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "roleA": role_a,
                "roleB": role_b,
                "appliesTo": applies_to,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        role_a = d.pop("roleA")

        role_b = d.pop("roleB")

        applies_to = d.pop("appliesTo")

        constraint_body = cls(
            role_a=role_a,
            role_b=role_b,
            applies_to=applies_to,
        )

        return constraint_body

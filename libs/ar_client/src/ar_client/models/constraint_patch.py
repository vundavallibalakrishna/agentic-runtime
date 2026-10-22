from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast


T = TypeVar("T", bound="ConstraintPatch")


@_attrs_define
class ConstraintPatch:
    """
    Attributes:
        enabled (bool | None | Unset):
        applies_to (None | str | Unset):
    """

    enabled: bool | None | Unset = UNSET
    applies_to: None | str | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        enabled: bool | None | Unset
        if isinstance(self.enabled, Unset):
            enabled = UNSET
        else:
            enabled = self.enabled

        applies_to: None | str | Unset
        if isinstance(self.applies_to, Unset):
            applies_to = UNSET
        else:
            applies_to = self.applies_to

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if enabled is not UNSET:
            field_dict["enabled"] = enabled
        if applies_to is not UNSET:
            field_dict["appliesTo"] = applies_to

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)

        def _parse_enabled(data: object) -> bool | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        enabled = _parse_enabled(d.pop("enabled", UNSET))

        def _parse_applies_to(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        applies_to = _parse_applies_to(d.pop("appliesTo", UNSET))

        constraint_patch = cls(
            enabled=enabled,
            applies_to=applies_to,
        )

        return constraint_patch

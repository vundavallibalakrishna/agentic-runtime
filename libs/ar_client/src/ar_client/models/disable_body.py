from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset


T = TypeVar("T", bound="DisableBody")


@_attrs_define
class DisableBody:
    """
    Attributes:
        reason (str):
        cancel_active (bool | Unset):  Default: True.
    """

    reason: str
    cancel_active: bool | Unset = True

    def to_dict(self) -> dict[str, Any]:
        reason = self.reason

        cancel_active = self.cancel_active

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "reason": reason,
            }
        )
        if cancel_active is not UNSET:
            field_dict["cancelActive"] = cancel_active

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        reason = d.pop("reason")

        cancel_active = d.pop("cancelActive", UNSET)

        disable_body = cls(
            reason=reason,
            cancel_active=cancel_active,
        )

        return disable_body

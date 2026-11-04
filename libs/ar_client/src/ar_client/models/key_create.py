from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset


T = TypeVar("T", bound="KeyCreate")


@_attrs_define
class KeyCreate:
    """
    Attributes:
        label (str):
        scope (str | Unset):  Default: 'agent'.
        rate_limit_rpm (int | Unset):  Default: 60.
        monthly_quota (int | Unset):  Default: 10000.
    """

    label: str
    scope: str | Unset = "agent"
    rate_limit_rpm: int | Unset = 60
    monthly_quota: int | Unset = 10000

    def to_dict(self) -> dict[str, Any]:
        label = self.label

        scope = self.scope

        rate_limit_rpm = self.rate_limit_rpm

        monthly_quota = self.monthly_quota

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "label": label,
            }
        )
        if scope is not UNSET:
            field_dict["scope"] = scope
        if rate_limit_rpm is not UNSET:
            field_dict["rateLimitRpm"] = rate_limit_rpm
        if monthly_quota is not UNSET:
            field_dict["monthlyQuota"] = monthly_quota

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        label = d.pop("label")

        scope = d.pop("scope", UNSET)

        rate_limit_rpm = d.pop("rateLimitRpm", UNSET)

        monthly_quota = d.pop("monthlyQuota", UNSET)

        key_create = cls(
            label=label,
            scope=scope,
            rate_limit_rpm=rate_limit_rpm,
            monthly_quota=monthly_quota,
        )

        return key_create

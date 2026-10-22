from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast


T = TypeVar("T", bound="QuotaPatch")


@_attrs_define
class QuotaPatch:
    """
    Attributes:
        limit_value (int | None | Unset):
        action (None | str | Unset):
        warn_at_pct (int | None | Unset):
    """

    limit_value: int | None | Unset = UNSET
    action: None | str | Unset = UNSET
    warn_at_pct: int | None | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        limit_value: int | None | Unset
        if isinstance(self.limit_value, Unset):
            limit_value = UNSET
        else:
            limit_value = self.limit_value

        action: None | str | Unset
        if isinstance(self.action, Unset):
            action = UNSET
        else:
            action = self.action

        warn_at_pct: int | None | Unset
        if isinstance(self.warn_at_pct, Unset):
            warn_at_pct = UNSET
        else:
            warn_at_pct = self.warn_at_pct

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if limit_value is not UNSET:
            field_dict["limitValue"] = limit_value
        if action is not UNSET:
            field_dict["action"] = action
        if warn_at_pct is not UNSET:
            field_dict["warnAtPct"] = warn_at_pct

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)

        def _parse_limit_value(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        limit_value = _parse_limit_value(d.pop("limitValue", UNSET))

        def _parse_action(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        action = _parse_action(d.pop("action", UNSET))

        def _parse_warn_at_pct(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        warn_at_pct = _parse_warn_at_pct(d.pop("warnAtPct", UNSET))

        quota_patch = cls(
            limit_value=limit_value,
            action=action,
            warn_at_pct=warn_at_pct,
        )

        return quota_patch

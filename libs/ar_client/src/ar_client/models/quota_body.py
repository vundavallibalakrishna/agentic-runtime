from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast
from uuid import UUID


T = TypeVar("T", bound="QuotaBody")


@_attrs_define
class QuotaBody:
    """
    Attributes:
        scope_type (str):
        metric (str):
        period (str):
        limit_value (int):
        scope_id (None | Unset | UUID):
        action (str | Unset):  Default: 'block'.
        warn_at_pct (int | Unset):  Default: 80.
    """

    scope_type: str
    metric: str
    period: str
    limit_value: int
    scope_id: None | Unset | UUID = UNSET
    action: str | Unset = "block"
    warn_at_pct: int | Unset = 80

    def to_dict(self) -> dict[str, Any]:
        scope_type = self.scope_type

        metric = self.metric

        period = self.period

        limit_value = self.limit_value

        scope_id: None | str | Unset
        if isinstance(self.scope_id, Unset):
            scope_id = UNSET
        elif isinstance(self.scope_id, UUID):
            scope_id = str(self.scope_id)
        else:
            scope_id = self.scope_id

        action = self.action

        warn_at_pct = self.warn_at_pct

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "scopeType": scope_type,
                "metric": metric,
                "period": period,
                "limitValue": limit_value,
            }
        )
        if scope_id is not UNSET:
            field_dict["scopeId"] = scope_id
        if action is not UNSET:
            field_dict["action"] = action
        if warn_at_pct is not UNSET:
            field_dict["warnAtPct"] = warn_at_pct

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        scope_type = d.pop("scopeType")

        metric = d.pop("metric")

        period = d.pop("period")

        limit_value = d.pop("limitValue")

        def _parse_scope_id(data: object) -> None | Unset | UUID:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                scope_id_type_0 = UUID(data)

                return scope_id_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(None | Unset | UUID, data)

        scope_id = _parse_scope_id(d.pop("scopeId", UNSET))

        action = d.pop("action", UNSET)

        warn_at_pct = d.pop("warnAtPct", UNSET)

        quota_body = cls(
            scope_type=scope_type,
            metric=metric,
            period=period,
            limit_value=limit_value,
            scope_id=scope_id,
            action=action,
            warn_at_pct=warn_at_pct,
        )

        return quota_body

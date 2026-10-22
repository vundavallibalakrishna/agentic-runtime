from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast

if TYPE_CHECKING:
    from ..models.trigger_body_config import TriggerBodyConfig


T = TypeVar("T", bound="TriggerBody")


@_attrs_define
class TriggerBody:
    """
    Attributes:
        type_ (str):
        cron (None | str | Unset):
        timezone (None | str | Unset):
        jitter_s (int | Unset):  Default: 0.
        catchup_window_s (int | Unset):  Default: 0.
        config (TriggerBodyConfig | Unset):
    """

    type_: str
    cron: None | str | Unset = UNSET
    timezone: None | str | Unset = UNSET
    jitter_s: int | Unset = 0
    catchup_window_s: int | Unset = 0
    config: TriggerBodyConfig | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        from ..models.trigger_body_config import TriggerBodyConfig  # noqa: PLC0415

        type_ = self.type_

        cron: None | str | Unset
        if isinstance(self.cron, Unset):
            cron = UNSET
        else:
            cron = self.cron

        timezone: None | str | Unset
        if isinstance(self.timezone, Unset):
            timezone = UNSET
        else:
            timezone = self.timezone

        jitter_s = self.jitter_s

        catchup_window_s = self.catchup_window_s

        config: dict[str, Any] | Unset = UNSET
        if not isinstance(self.config, Unset):
            config = self.config.to_dict()

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "type": type_,
            }
        )
        if cron is not UNSET:
            field_dict["cron"] = cron
        if timezone is not UNSET:
            field_dict["timezone"] = timezone
        if jitter_s is not UNSET:
            field_dict["jitterS"] = jitter_s
        if catchup_window_s is not UNSET:
            field_dict["catchupWindowS"] = catchup_window_s
        if config is not UNSET:
            field_dict["config"] = config

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.trigger_body_config import TriggerBodyConfig  # noqa: PLC0415

        d = dict(src_dict)
        type_ = d.pop("type")

        def _parse_cron(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        cron = _parse_cron(d.pop("cron", UNSET))

        def _parse_timezone(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        timezone = _parse_timezone(d.pop("timezone", UNSET))

        jitter_s = d.pop("jitterS", UNSET)

        catchup_window_s = d.pop("catchupWindowS", UNSET)

        _config = d.pop("config", UNSET)
        config: TriggerBodyConfig | Unset
        if isinstance(_config, Unset):
            config = UNSET
        else:
            config = TriggerBodyConfig.from_dict(_config)

        trigger_body = cls(
            type_=type_,
            cron=cron,
            timezone=timezone,
            jitter_s=jitter_s,
            catchup_window_s=catchup_window_s,
            config=config,
        )

        return trigger_body

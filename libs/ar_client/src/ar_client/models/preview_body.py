from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset


T = TypeVar("T", bound="PreviewBody")


@_attrs_define
class PreviewBody:
    """
    Attributes:
        cron (str):
        timezone (str):
    """

    cron: str
    timezone: str

    def to_dict(self) -> dict[str, Any]:
        cron = self.cron

        timezone = self.timezone

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "cron": cron,
                "timezone": timezone,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        cron = d.pop("cron")

        timezone = d.pop("timezone")

        preview_body = cls(
            cron=cron,
            timezone=timezone,
        )

        return preview_body

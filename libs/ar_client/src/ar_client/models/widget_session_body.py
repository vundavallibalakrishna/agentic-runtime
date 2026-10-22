from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from uuid import UUID


T = TypeVar("T", bound="WidgetSessionBody")


@_attrs_define
class WidgetSessionBody:
    """
    Attributes:
        integration_id (UUID):
        token (str):
    """

    integration_id: UUID
    token: str

    def to_dict(self) -> dict[str, Any]:
        integration_id = str(self.integration_id)

        token = self.token

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "integrationId": integration_id,
                "token": token,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        integration_id = UUID(d.pop("integrationId"))

        token = d.pop("token")

        widget_session_body = cls(
            integration_id=integration_id,
            token=token,
        )

        return widget_session_body

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast
from uuid import UUID


T = TypeVar("T", bound="WidgetSessionBody")


@_attrs_define
class WidgetSessionBody:
    """
    Attributes:
        integration_id (UUID):
        token (None | str | Unset):
    """

    integration_id: UUID
    token: None | str | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        integration_id = str(self.integration_id)

        token: None | str | Unset
        if isinstance(self.token, Unset):
            token = UNSET
        else:
            token = self.token

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "integrationId": integration_id,
            }
        )
        if token is not UNSET:
            field_dict["token"] = token

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        integration_id = UUID(d.pop("integrationId"))

        def _parse_token(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        token = _parse_token(d.pop("token", UNSET))

        widget_session_body = cls(
            integration_id=integration_id,
            token=token,
        )

        return widget_session_body

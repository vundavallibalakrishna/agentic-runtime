from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from uuid import UUID


T = TypeVar("T", bound="ProbeBody")


@_attrs_define
class ProbeBody:
    """
    Attributes:
        connection_id (UUID):
    """

    connection_id: UUID

    def to_dict(self) -> dict[str, Any]:
        connection_id = str(self.connection_id)

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "connectionId": connection_id,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        connection_id = UUID(d.pop("connectionId"))

        probe_body = cls(
            connection_id=connection_id,
        )

        return probe_body

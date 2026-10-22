from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast
from uuid import UUID


T = TypeVar("T", bound="AliasBody")


@_attrs_define
class AliasBody:
    """
    Attributes:
        alias (str):
        primary_model_id (UUID):
        kind (str | Unset):  Default: 'chat'.
        fallback_model_ids (list[UUID] | Unset):
    """

    alias: str
    primary_model_id: UUID
    kind: str | Unset = "chat"
    fallback_model_ids: list[UUID] | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        alias = self.alias

        primary_model_id = str(self.primary_model_id)

        kind = self.kind

        fallback_model_ids: list[str] | Unset = UNSET
        if not isinstance(self.fallback_model_ids, Unset):
            fallback_model_ids = []
            for fallback_model_ids_item_data in self.fallback_model_ids:
                fallback_model_ids_item = str(fallback_model_ids_item_data)
                fallback_model_ids.append(fallback_model_ids_item)

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "alias": alias,
                "primaryModelId": primary_model_id,
            }
        )
        if kind is not UNSET:
            field_dict["kind"] = kind
        if fallback_model_ids is not UNSET:
            field_dict["fallbackModelIds"] = fallback_model_ids

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        alias = d.pop("alias")

        primary_model_id = UUID(d.pop("primaryModelId"))

        kind = d.pop("kind", UNSET)

        _fallback_model_ids = d.pop("fallbackModelIds", UNSET)
        fallback_model_ids: list[UUID] | Unset = UNSET
        if _fallback_model_ids is not UNSET:
            fallback_model_ids = []
            for fallback_model_ids_item_data in _fallback_model_ids:
                fallback_model_ids_item = UUID(fallback_model_ids_item_data)

                fallback_model_ids.append(fallback_model_ids_item)

        alias_body = cls(
            alias=alias,
            primary_model_id=primary_model_id,
            kind=kind,
            fallback_model_ids=fallback_model_ids,
        )

        return alias_body

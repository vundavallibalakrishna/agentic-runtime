from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast
from uuid import UUID


T = TypeVar("T", bound="AliasPatch")


@_attrs_define
class AliasPatch:
    """
    Attributes:
        primary_model_id (UUID):
        fallback_model_ids (list[UUID] | None | Unset):
    """

    primary_model_id: UUID
    fallback_model_ids: list[UUID] | None | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        primary_model_id = str(self.primary_model_id)

        fallback_model_ids: list[str] | None | Unset
        if isinstance(self.fallback_model_ids, Unset):
            fallback_model_ids = UNSET
        elif isinstance(self.fallback_model_ids, list):
            fallback_model_ids = []
            for fallback_model_ids_type_0_item_data in self.fallback_model_ids:
                fallback_model_ids_type_0_item = str(fallback_model_ids_type_0_item_data)
                fallback_model_ids.append(fallback_model_ids_type_0_item)

        else:
            fallback_model_ids = self.fallback_model_ids

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "primaryModelId": primary_model_id,
            }
        )
        if fallback_model_ids is not UNSET:
            field_dict["fallbackModelIds"] = fallback_model_ids

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        primary_model_id = UUID(d.pop("primaryModelId"))

        def _parse_fallback_model_ids(data: object) -> list[UUID] | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                fallback_model_ids_type_0 = []
                _fallback_model_ids_type_0 = data
                for fallback_model_ids_type_0_item_data in _fallback_model_ids_type_0:
                    fallback_model_ids_type_0_item = UUID(fallback_model_ids_type_0_item_data)

                    fallback_model_ids_type_0.append(fallback_model_ids_type_0_item)

                return fallback_model_ids_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(list[UUID] | None | Unset, data)

        fallback_model_ids = _parse_fallback_model_ids(d.pop("fallbackModelIds", UNSET))

        alias_patch = cls(
            primary_model_id=primary_model_id,
            fallback_model_ids=fallback_model_ids,
        )

        return alias_patch

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from uuid import UUID


T = TypeVar("T", bound="ModelBody")


@_attrs_define
class ModelBody:
    """
    Attributes:
        provider_id (UUID):
        name (str):
        upstream_model (str):
        kind (str | Unset):  Default: 'chat'.
        price_input_micros_per_mtok (int | Unset):  Default: 0.
        price_output_micros_per_mtok (int | Unset):  Default: 0.
    """

    provider_id: UUID
    name: str
    upstream_model: str
    kind: str | Unset = "chat"
    price_input_micros_per_mtok: int | Unset = 0
    price_output_micros_per_mtok: int | Unset = 0

    def to_dict(self) -> dict[str, Any]:
        provider_id = str(self.provider_id)

        name = self.name

        upstream_model = self.upstream_model

        kind = self.kind

        price_input_micros_per_mtok = self.price_input_micros_per_mtok

        price_output_micros_per_mtok = self.price_output_micros_per_mtok

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "providerId": provider_id,
                "name": name,
                "upstreamModel": upstream_model,
            }
        )
        if kind is not UNSET:
            field_dict["kind"] = kind
        if price_input_micros_per_mtok is not UNSET:
            field_dict["priceInputMicrosPerMtok"] = price_input_micros_per_mtok
        if price_output_micros_per_mtok is not UNSET:
            field_dict["priceOutputMicrosPerMtok"] = price_output_micros_per_mtok

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        provider_id = UUID(d.pop("providerId"))

        name = d.pop("name")

        upstream_model = d.pop("upstreamModel")

        kind = d.pop("kind", UNSET)

        price_input_micros_per_mtok = d.pop("priceInputMicrosPerMtok", UNSET)

        price_output_micros_per_mtok = d.pop("priceOutputMicrosPerMtok", UNSET)

        model_body = cls(
            provider_id=provider_id,
            name=name,
            upstream_model=upstream_model,
            kind=kind,
            price_input_micros_per_mtok=price_input_micros_per_mtok,
            price_output_micros_per_mtok=price_output_micros_per_mtok,
        )

        return model_body

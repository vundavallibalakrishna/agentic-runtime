from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast

if TYPE_CHECKING:
    from ..models.model_patch_request_options_type_0 import ModelPatchRequestOptionsType0


T = TypeVar("T", bound="ModelPatch")


@_attrs_define
class ModelPatch:
    """
    Attributes:
        name (None | str | Unset):
        upstream_model (None | str | Unset):
        price_input_micros_per_mtok (int | None | Unset):
        price_output_micros_per_mtok (int | None | Unset):
        request_options (ModelPatchRequestOptionsType0 | None | Unset):
        embedding_dimensions (int | None | Unset):
    """

    name: None | str | Unset = UNSET
    upstream_model: None | str | Unset = UNSET
    price_input_micros_per_mtok: int | None | Unset = UNSET
    price_output_micros_per_mtok: int | None | Unset = UNSET
    request_options: ModelPatchRequestOptionsType0 | None | Unset = UNSET
    embedding_dimensions: int | None | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        from ..models.model_patch_request_options_type_0 import ModelPatchRequestOptionsType0  # noqa: PLC0415

        name: None | str | Unset
        if isinstance(self.name, Unset):
            name = UNSET
        else:
            name = self.name

        upstream_model: None | str | Unset
        if isinstance(self.upstream_model, Unset):
            upstream_model = UNSET
        else:
            upstream_model = self.upstream_model

        price_input_micros_per_mtok: int | None | Unset
        if isinstance(self.price_input_micros_per_mtok, Unset):
            price_input_micros_per_mtok = UNSET
        else:
            price_input_micros_per_mtok = self.price_input_micros_per_mtok

        price_output_micros_per_mtok: int | None | Unset
        if isinstance(self.price_output_micros_per_mtok, Unset):
            price_output_micros_per_mtok = UNSET
        else:
            price_output_micros_per_mtok = self.price_output_micros_per_mtok

        request_options: dict[str, Any] | None | Unset
        if isinstance(self.request_options, Unset):
            request_options = UNSET
        elif isinstance(self.request_options, ModelPatchRequestOptionsType0):
            request_options = self.request_options.to_dict()
        else:
            request_options = self.request_options

        embedding_dimensions: int | None | Unset
        if isinstance(self.embedding_dimensions, Unset):
            embedding_dimensions = UNSET
        else:
            embedding_dimensions = self.embedding_dimensions

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if name is not UNSET:
            field_dict["name"] = name
        if upstream_model is not UNSET:
            field_dict["upstreamModel"] = upstream_model
        if price_input_micros_per_mtok is not UNSET:
            field_dict["priceInputMicrosPerMtok"] = price_input_micros_per_mtok
        if price_output_micros_per_mtok is not UNSET:
            field_dict["priceOutputMicrosPerMtok"] = price_output_micros_per_mtok
        if request_options is not UNSET:
            field_dict["requestOptions"] = request_options
        if embedding_dimensions is not UNSET:
            field_dict["embeddingDimensions"] = embedding_dimensions

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.model_patch_request_options_type_0 import ModelPatchRequestOptionsType0  # noqa: PLC0415

        d = dict(src_dict)

        def _parse_name(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        name = _parse_name(d.pop("name", UNSET))

        def _parse_upstream_model(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        upstream_model = _parse_upstream_model(d.pop("upstreamModel", UNSET))

        def _parse_price_input_micros_per_mtok(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        price_input_micros_per_mtok = _parse_price_input_micros_per_mtok(
            d.pop("priceInputMicrosPerMtok", UNSET)
        )

        def _parse_price_output_micros_per_mtok(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        price_output_micros_per_mtok = _parse_price_output_micros_per_mtok(
            d.pop("priceOutputMicrosPerMtok", UNSET)
        )

        def _parse_request_options(data: object) -> ModelPatchRequestOptionsType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                request_options_type_0 = ModelPatchRequestOptionsType0.from_dict(data)

                return request_options_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(ModelPatchRequestOptionsType0 | None | Unset, data)

        request_options = _parse_request_options(d.pop("requestOptions", UNSET))

        def _parse_embedding_dimensions(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        embedding_dimensions = _parse_embedding_dimensions(d.pop("embeddingDimensions", UNSET))

        model_patch = cls(
            name=name,
            upstream_model=upstream_model,
            price_input_micros_per_mtok=price_input_micros_per_mtok,
            price_output_micros_per_mtok=price_output_micros_per_mtok,
            request_options=request_options,
            embedding_dimensions=embedding_dimensions,
        )

        return model_patch

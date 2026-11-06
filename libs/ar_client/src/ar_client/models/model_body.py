from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast
from uuid import UUID

if TYPE_CHECKING:
    from ..models.model_body_request_options_type_0 import ModelBodyRequestOptionsType0


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
        request_options (ModelBodyRequestOptionsType0 | None | Unset):
        embedding_dimensions (int | None | Unset):
        capabilities (list[str] | None | Unset):
    """

    provider_id: UUID
    name: str
    upstream_model: str
    kind: str | Unset = "chat"
    price_input_micros_per_mtok: int | Unset = 0
    price_output_micros_per_mtok: int | Unset = 0
    request_options: ModelBodyRequestOptionsType0 | None | Unset = UNSET
    embedding_dimensions: int | None | Unset = UNSET
    capabilities: list[str] | None | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        from ..models.model_body_request_options_type_0 import ModelBodyRequestOptionsType0  # noqa: PLC0415

        provider_id = str(self.provider_id)

        name = self.name

        upstream_model = self.upstream_model

        kind = self.kind

        price_input_micros_per_mtok = self.price_input_micros_per_mtok

        price_output_micros_per_mtok = self.price_output_micros_per_mtok

        request_options: dict[str, Any] | None | Unset
        if isinstance(self.request_options, Unset):
            request_options = UNSET
        elif isinstance(self.request_options, ModelBodyRequestOptionsType0):
            request_options = self.request_options.to_dict()
        else:
            request_options = self.request_options

        embedding_dimensions: int | None | Unset
        if isinstance(self.embedding_dimensions, Unset):
            embedding_dimensions = UNSET
        else:
            embedding_dimensions = self.embedding_dimensions

        capabilities: list[str] | None | Unset
        if isinstance(self.capabilities, Unset):
            capabilities = UNSET
        elif isinstance(self.capabilities, list):
            capabilities = self.capabilities

        else:
            capabilities = self.capabilities

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
        if request_options is not UNSET:
            field_dict["requestOptions"] = request_options
        if embedding_dimensions is not UNSET:
            field_dict["embeddingDimensions"] = embedding_dimensions
        if capabilities is not UNSET:
            field_dict["capabilities"] = capabilities

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.model_body_request_options_type_0 import ModelBodyRequestOptionsType0  # noqa: PLC0415

        d = dict(src_dict)
        provider_id = UUID(d.pop("providerId"))

        name = d.pop("name")

        upstream_model = d.pop("upstreamModel")

        kind = d.pop("kind", UNSET)

        price_input_micros_per_mtok = d.pop("priceInputMicrosPerMtok", UNSET)

        price_output_micros_per_mtok = d.pop("priceOutputMicrosPerMtok", UNSET)

        def _parse_request_options(data: object) -> ModelBodyRequestOptionsType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                request_options_type_0 = ModelBodyRequestOptionsType0.from_dict(data)

                return request_options_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(ModelBodyRequestOptionsType0 | None | Unset, data)

        request_options = _parse_request_options(d.pop("requestOptions", UNSET))

        def _parse_embedding_dimensions(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        embedding_dimensions = _parse_embedding_dimensions(d.pop("embeddingDimensions", UNSET))

        def _parse_capabilities(data: object) -> list[str] | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                capabilities_type_0 = cast(list[str], data)

                return capabilities_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(list[str] | None | Unset, data)

        capabilities = _parse_capabilities(d.pop("capabilities", UNSET))

        model_body = cls(
            provider_id=provider_id,
            name=name,
            upstream_model=upstream_model,
            kind=kind,
            price_input_micros_per_mtok=price_input_micros_per_mtok,
            price_output_micros_per_mtok=price_output_micros_per_mtok,
            request_options=request_options,
            embedding_dimensions=embedding_dimensions,
            capabilities=capabilities,
        )

        return model_body

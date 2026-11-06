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
    from ..models.alias_body_default_params_type_0 import AliasBodyDefaultParamsType0


T = TypeVar("T", bound="AliasBody")


@_attrs_define
class AliasBody:
    """
    Attributes:
        alias (str):
        primary_model_id (UUID):
        kind (str | Unset):  Default: 'chat'.
        fallback_model_ids (list[UUID] | Unset):
        default_params (AliasBodyDefaultParamsType0 | None | Unset):
    """

    alias: str
    primary_model_id: UUID
    kind: str | Unset = "chat"
    fallback_model_ids: list[UUID] | Unset = UNSET
    default_params: AliasBodyDefaultParamsType0 | None | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        from ..models.alias_body_default_params_type_0 import AliasBodyDefaultParamsType0  # noqa: PLC0415

        alias = self.alias

        primary_model_id = str(self.primary_model_id)

        kind = self.kind

        fallback_model_ids: list[str] | Unset = UNSET
        if not isinstance(self.fallback_model_ids, Unset):
            fallback_model_ids = []
            for fallback_model_ids_item_data in self.fallback_model_ids:
                fallback_model_ids_item = str(fallback_model_ids_item_data)
                fallback_model_ids.append(fallback_model_ids_item)

        default_params: dict[str, Any] | None | Unset
        if isinstance(self.default_params, Unset):
            default_params = UNSET
        elif isinstance(self.default_params, AliasBodyDefaultParamsType0):
            default_params = self.default_params.to_dict()
        else:
            default_params = self.default_params

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
        if default_params is not UNSET:
            field_dict["defaultParams"] = default_params

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.alias_body_default_params_type_0 import AliasBodyDefaultParamsType0  # noqa: PLC0415

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

        def _parse_default_params(data: object) -> AliasBodyDefaultParamsType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                default_params_type_0 = AliasBodyDefaultParamsType0.from_dict(data)

                return default_params_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(AliasBodyDefaultParamsType0 | None | Unset, data)

        default_params = _parse_default_params(d.pop("defaultParams", UNSET))

        alias_body = cls(
            alias=alias,
            primary_model_id=primary_model_id,
            kind=kind,
            fallback_model_ids=fallback_model_ids,
            default_params=default_params,
        )

        return alias_body

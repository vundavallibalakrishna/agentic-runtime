from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from typing import cast

if TYPE_CHECKING:
    from ..models.masking_kind import MaskingKind


T = TypeVar("T", bound="MaskingView")


@_attrs_define
class MaskingView:
    """
    Attributes:
        enabled (bool):
        uses_default (bool):
        min_score (float):
        default_min_score (float):
        kinds (list[MaskingKind]):
    """

    enabled: bool
    uses_default: bool
    min_score: float
    default_min_score: float
    kinds: list[MaskingKind]

    def to_dict(self) -> dict[str, Any]:
        from ..models.masking_kind import MaskingKind  # noqa: PLC0415

        enabled = self.enabled

        uses_default = self.uses_default

        min_score = self.min_score

        default_min_score = self.default_min_score

        kinds = []
        for kinds_item_data in self.kinds:
            kinds_item = kinds_item_data.to_dict()
            kinds.append(kinds_item)

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "enabled": enabled,
                "usesDefault": uses_default,
                "minScore": min_score,
                "defaultMinScore": default_min_score,
                "kinds": kinds,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.masking_kind import MaskingKind  # noqa: PLC0415

        d = dict(src_dict)
        enabled = d.pop("enabled")

        uses_default = d.pop("usesDefault")

        min_score = d.pop("minScore")

        default_min_score = d.pop("defaultMinScore")

        kinds = []
        _kinds = d.pop("kinds")
        for kinds_item_data in _kinds:
            kinds_item = MaskingKind.from_dict(kinds_item_data)

            kinds.append(kinds_item)

        masking_view = cls(
            enabled=enabled,
            uses_default=uses_default,
            min_score=min_score,
            default_min_score=default_min_score,
            kinds=kinds,
        )

        return masking_view

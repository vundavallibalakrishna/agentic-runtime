from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast


T = TypeVar("T", bound="CardPatch")


@_attrs_define
class CardPatch:
    """
    Attributes:
        known_limitations (None | str | Unset):
        review_due_at (None | str | Unset):
        data_categories (list[str] | None | Unset):
    """

    known_limitations: None | str | Unset = UNSET
    review_due_at: None | str | Unset = UNSET
    data_categories: list[str] | None | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        known_limitations: None | str | Unset
        if isinstance(self.known_limitations, Unset):
            known_limitations = UNSET
        else:
            known_limitations = self.known_limitations

        review_due_at: None | str | Unset
        if isinstance(self.review_due_at, Unset):
            review_due_at = UNSET
        else:
            review_due_at = self.review_due_at

        data_categories: list[str] | None | Unset
        if isinstance(self.data_categories, Unset):
            data_categories = UNSET
        elif isinstance(self.data_categories, list):
            data_categories = self.data_categories

        else:
            data_categories = self.data_categories

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if known_limitations is not UNSET:
            field_dict["knownLimitations"] = known_limitations
        if review_due_at is not UNSET:
            field_dict["reviewDueAt"] = review_due_at
        if data_categories is not UNSET:
            field_dict["dataCategories"] = data_categories

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)

        def _parse_known_limitations(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        known_limitations = _parse_known_limitations(d.pop("knownLimitations", UNSET))

        def _parse_review_due_at(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        review_due_at = _parse_review_due_at(d.pop("reviewDueAt", UNSET))

        def _parse_data_categories(data: object) -> list[str] | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                data_categories_type_0 = cast(list[str], data)

                return data_categories_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(list[str] | None | Unset, data)

        data_categories = _parse_data_categories(d.pop("dataCategories", UNSET))

        card_patch = cls(
            known_limitations=known_limitations,
            review_due_at=review_due_at,
            data_categories=data_categories,
        )

        return card_patch

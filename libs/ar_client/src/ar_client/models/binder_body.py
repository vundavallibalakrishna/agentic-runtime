from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast

if TYPE_CHECKING:
    from ..models.binder_body_selection import BinderBodySelection


T = TypeVar("T", bound="BinderBody")


@_attrs_define
class BinderBody:
    """
    Attributes:
        title (str):
        selection (BinderBodySelection):
        require_review (bool | Unset):  Default: False.
    """

    title: str
    selection: BinderBodySelection
    require_review: bool | Unset = False

    def to_dict(self) -> dict[str, Any]:
        from ..models.binder_body_selection import BinderBodySelection  # noqa: PLC0415

        title = self.title

        selection = self.selection.to_dict()

        require_review = self.require_review

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "title": title,
                "selection": selection,
            }
        )
        if require_review is not UNSET:
            field_dict["requireReview"] = require_review

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.binder_body_selection import BinderBodySelection  # noqa: PLC0415

        d = dict(src_dict)
        title = d.pop("title")

        selection = BinderBodySelection.from_dict(d.pop("selection"))

        require_review = d.pop("requireReview", UNSET)

        binder_body = cls(
            title=title,
            selection=selection,
            require_review=require_review,
        )

        return binder_body

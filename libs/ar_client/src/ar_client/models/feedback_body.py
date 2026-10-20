from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset






T = TypeVar("T", bound="FeedbackBody")



@_attrs_define
class FeedbackBody:
    """ 
        Attributes:
            rating (str):
            comment (str | Unset):  Default: ''.
     """

    rating: str
    comment: str | Unset = ''





    def to_dict(self) -> dict[str, Any]:
        rating = self.rating

        comment = self.comment


        field_dict: dict[str, Any] = {}

        field_dict.update({
            "rating": rating,
        })
        if comment is not UNSET:
            field_dict["comment"] = comment

        return field_dict



    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        rating = d.pop("rating")

        comment = d.pop("comment", UNSET)

        feedback_body = cls(
            rating=rating,
            comment=comment,
        )

        return feedback_body


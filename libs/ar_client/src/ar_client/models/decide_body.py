from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset


T = TypeVar("T", bound="DecideBody")


@_attrs_define
class DecideBody:
    """
    Attributes:
        decision (str):
        hunk_id (str | Unset):  Default: ''.
    """

    decision: str
    hunk_id: str | Unset = ""

    def to_dict(self) -> dict[str, Any]:
        decision = self.decision

        hunk_id = self.hunk_id

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "decision": decision,
            }
        )
        if hunk_id is not UNSET:
            field_dict["hunkId"] = hunk_id

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        decision = d.pop("decision")

        hunk_id = d.pop("hunkId", UNSET)

        decide_body = cls(
            decision=decision,
            hunk_id=hunk_id,
        )

        return decide_body

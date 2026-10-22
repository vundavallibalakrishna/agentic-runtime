from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define

from ..types import UNSET, Unset

T = TypeVar("T", bound="PublishBody")


@_attrs_define
class PublishBody:
    """
    Attributes:
        change_note (str | Unset):  Default: ''.
        skip_eval_gate (bool | Unset):  Default: False.
    """

    change_note: str | Unset = ""
    skip_eval_gate: bool | Unset = False

    def to_dict(self) -> dict[str, Any]:
        change_note = self.change_note

        skip_eval_gate = self.skip_eval_gate

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if change_note is not UNSET:
            field_dict["changeNote"] = change_note
        if skip_eval_gate is not UNSET:
            field_dict["skipEvalGate"] = skip_eval_gate

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        change_note = d.pop("changeNote", UNSET)

        skip_eval_gate = d.pop("skipEvalGate", UNSET)

        publish_body = cls(
            change_note=change_note,
            skip_eval_gate=skip_eval_gate,
        )

        return publish_body

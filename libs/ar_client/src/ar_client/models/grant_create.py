from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset






T = TypeVar("T", bound="GrantCreate")



@_attrs_define
class GrantCreate:
    """ 
        Attributes:
            operator_subject (str):
            operator_email (str):
            level (str):
            reason (str):
            hours (int | Unset):  Default: 8.
     """

    operator_subject: str
    operator_email: str
    level: str
    reason: str
    hours: int | Unset = 8





    def to_dict(self) -> dict[str, Any]:
        operator_subject = self.operator_subject

        operator_email = self.operator_email

        level = self.level

        reason = self.reason

        hours = self.hours


        field_dict: dict[str, Any] = {}

        field_dict.update({
            "operatorSubject": operator_subject,
            "operatorEmail": operator_email,
            "level": level,
            "reason": reason,
        })
        if hours is not UNSET:
            field_dict["hours"] = hours

        return field_dict



    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        operator_subject = d.pop("operatorSubject")

        operator_email = d.pop("operatorEmail")

        level = d.pop("level")

        reason = d.pop("reason")

        hours = d.pop("hours", UNSET)

        grant_create = cls(
            operator_subject=operator_subject,
            operator_email=operator_email,
            level=level,
            reason=reason,
            hours=hours,
        )

        return grant_create


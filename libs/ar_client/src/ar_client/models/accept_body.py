from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast


T = TypeVar("T", bound="AcceptBody")


@_attrs_define
class AcceptBody:
    """
    Attributes:
        statement (None | str | Unset):
        comment (str | Unset):  Default: ''.
    """

    statement: None | str | Unset = UNSET
    comment: str | Unset = ""

    def to_dict(self) -> dict[str, Any]:
        statement: None | str | Unset
        if isinstance(self.statement, Unset):
            statement = UNSET
        else:
            statement = self.statement

        comment = self.comment

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if statement is not UNSET:
            field_dict["statement"] = statement
        if comment is not UNSET:
            field_dict["comment"] = comment

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)

        def _parse_statement(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        statement = _parse_statement(d.pop("statement", UNSET))

        comment = d.pop("comment", UNSET)

        accept_body = cls(
            statement=statement,
            comment=comment,
        )

        return accept_body

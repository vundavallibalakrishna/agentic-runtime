from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast
from uuid import UUID


T = TypeVar("T", bound="ReviewDecideBody")


@_attrs_define
class ReviewDecideBody:
    """
    Attributes:
        decision (str):
        content_hash (str):
        statement_hash (str):
        comment (str | Unset):  Default: ''.
        delegated_to_user_id (None | Unset | UUID):
    """

    decision: str
    content_hash: str
    statement_hash: str
    comment: str | Unset = ""
    delegated_to_user_id: None | Unset | UUID = UNSET

    def to_dict(self) -> dict[str, Any]:
        decision = self.decision

        content_hash = self.content_hash

        statement_hash = self.statement_hash

        comment = self.comment

        delegated_to_user_id: None | str | Unset
        if isinstance(self.delegated_to_user_id, Unset):
            delegated_to_user_id = UNSET
        elif isinstance(self.delegated_to_user_id, UUID):
            delegated_to_user_id = str(self.delegated_to_user_id)
        else:
            delegated_to_user_id = self.delegated_to_user_id

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "decision": decision,
                "contentHash": content_hash,
                "statementHash": statement_hash,
            }
        )
        if comment is not UNSET:
            field_dict["comment"] = comment
        if delegated_to_user_id is not UNSET:
            field_dict["delegatedToUserId"] = delegated_to_user_id

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        decision = d.pop("decision")

        content_hash = d.pop("contentHash")

        statement_hash = d.pop("statementHash")

        comment = d.pop("comment", UNSET)

        def _parse_delegated_to_user_id(data: object) -> None | Unset | UUID:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                delegated_to_user_id_type_0 = UUID(data)

                return delegated_to_user_id_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(None | Unset | UUID, data)

        delegated_to_user_id = _parse_delegated_to_user_id(d.pop("delegatedToUserId", UNSET))

        review_decide_body = cls(
            decision=decision,
            content_hash=content_hash,
            statement_hash=statement_hash,
            comment=comment,
            delegated_to_user_id=delegated_to_user_id,
        )

        return review_decide_body

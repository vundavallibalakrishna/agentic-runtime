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
    from ..models.hold_body_scopequery import HoldBodyScopequery


T = TypeVar("T", bound="HoldBody")


@_attrs_define
class HoldBody:
    """
    Attributes:
        matter (str):
        scope_query (HoldBodyScopequery):
        approver_user_id (UUID):
        custodians (list[UUID] | Unset):
    """

    matter: str
    scope_query: HoldBodyScopequery
    approver_user_id: UUID
    custodians: list[UUID] | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        from ..models.hold_body_scopequery import HoldBodyScopequery  # noqa: PLC0415

        matter = self.matter

        scope_query = self.scope_query.to_dict()

        approver_user_id = str(self.approver_user_id)

        custodians: list[str] | Unset = UNSET
        if not isinstance(self.custodians, Unset):
            custodians = []
            for custodians_item_data in self.custodians:
                custodians_item = str(custodians_item_data)
                custodians.append(custodians_item)

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "matter": matter,
                "scopeQuery": scope_query,
                "approverUserId": approver_user_id,
            }
        )
        if custodians is not UNSET:
            field_dict["custodians"] = custodians

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.hold_body_scopequery import HoldBodyScopequery  # noqa: PLC0415

        d = dict(src_dict)
        matter = d.pop("matter")

        scope_query = HoldBodyScopequery.from_dict(d.pop("scopeQuery"))

        approver_user_id = UUID(d.pop("approverUserId"))

        _custodians = d.pop("custodians", UNSET)
        custodians: list[UUID] | Unset = UNSET
        if _custodians is not UNSET:
            custodians = []
            for custodians_item_data in _custodians:
                custodians_item = UUID(custodians_item_data)

                custodians.append(custodians_item)

        hold_body = cls(
            matter=matter,
            scope_query=scope_query,
            approver_user_id=approver_user_id,
            custodians=custodians,
        )

        return hold_body

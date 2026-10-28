from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast

if TYPE_CHECKING:
    from ..models.guest_body_grants_item import GuestBodyGrantsItem


T = TypeVar("T", bound="GuestBody")


@_attrs_define
class GuestBody:
    """
    Attributes:
        email (str):
        display_name (str):
        kind (str | Unset):  Default: 'external'.
        auth_method (str | Unset):  Default: 'magic_link_totp'.
        expires_at (str | Unset):  Default: ''.
        grants (list[GuestBodyGrantsItem] | Unset):
    """

    email: str
    display_name: str
    kind: str | Unset = "external"
    auth_method: str | Unset = "magic_link_totp"
    expires_at: str | Unset = ""
    grants: list[GuestBodyGrantsItem] | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        from ..models.guest_body_grants_item import GuestBodyGrantsItem  # noqa: PLC0415

        email = self.email

        display_name = self.display_name

        kind = self.kind

        auth_method = self.auth_method

        expires_at = self.expires_at

        grants: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.grants, Unset):
            grants = []
            for grants_item_data in self.grants:
                grants_item = grants_item_data.to_dict()
                grants.append(grants_item)

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "email": email,
                "displayName": display_name,
            }
        )
        if kind is not UNSET:
            field_dict["kind"] = kind
        if auth_method is not UNSET:
            field_dict["authMethod"] = auth_method
        if expires_at is not UNSET:
            field_dict["expiresAt"] = expires_at
        if grants is not UNSET:
            field_dict["grants"] = grants

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.guest_body_grants_item import GuestBodyGrantsItem  # noqa: PLC0415

        d = dict(src_dict)
        email = d.pop("email")

        display_name = d.pop("displayName")

        kind = d.pop("kind", UNSET)

        auth_method = d.pop("authMethod", UNSET)

        expires_at = d.pop("expiresAt", UNSET)

        _grants = d.pop("grants", UNSET)
        grants: list[GuestBodyGrantsItem] | Unset = UNSET
        if _grants is not UNSET:
            grants = []
            for grants_item_data in _grants:
                grants_item = GuestBodyGrantsItem.from_dict(grants_item_data)

                grants.append(grants_item)

        guest_body = cls(
            email=email,
            display_name=display_name,
            kind=kind,
            auth_method=auth_method,
            expires_at=expires_at,
            grants=grants,
        )

        return guest_body

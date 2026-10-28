from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast

if TYPE_CHECKING:
    from ..models.grant_body_scope import GrantBodyScope


T = TypeVar("T", bound="GrantBody")


@_attrs_define
class GrantBody:
    """
    Attributes:
        scope (GrantBodyScope):
        portal (str | Unset):  Default: 'records'.
        expires_at (str | Unset):  Default: ''.
        watermark (bool | Unset):  Default: True.
    """

    scope: GrantBodyScope
    portal: str | Unset = "records"
    expires_at: str | Unset = ""
    watermark: bool | Unset = True

    def to_dict(self) -> dict[str, Any]:
        from ..models.grant_body_scope import GrantBodyScope  # noqa: PLC0415

        scope = self.scope.to_dict()

        portal = self.portal

        expires_at = self.expires_at

        watermark = self.watermark

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "scope": scope,
            }
        )
        if portal is not UNSET:
            field_dict["portal"] = portal
        if expires_at is not UNSET:
            field_dict["expiresAt"] = expires_at
        if watermark is not UNSET:
            field_dict["watermark"] = watermark

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.grant_body_scope import GrantBodyScope  # noqa: PLC0415

        d = dict(src_dict)
        scope = GrantBodyScope.from_dict(d.pop("scope"))

        portal = d.pop("portal", UNSET)

        expires_at = d.pop("expiresAt", UNSET)

        watermark = d.pop("watermark", UNSET)

        grant_body = cls(
            scope=scope,
            portal=portal,
            expires_at=expires_at,
            watermark=watermark,
        )

        return grant_body

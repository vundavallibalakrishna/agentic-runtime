from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast

if TYPE_CHECKING:
    from ..models.credential_provider_patch_extra_type_0 import CredentialProviderPatchExtraType0


T = TypeVar("T", bound="CredentialProviderPatch")


@_attrs_define
class CredentialProviderPatch:
    """
    Attributes:
        name (None | str | Unset):
        authorize_url (None | str | Unset):
        token_url (None | str | Unset):
        client_id (None | str | Unset):
        status (None | str | Unset):
        extra (CredentialProviderPatchExtraType0 | None | Unset):
    """

    name: None | str | Unset = UNSET
    authorize_url: None | str | Unset = UNSET
    token_url: None | str | Unset = UNSET
    client_id: None | str | Unset = UNSET
    status: None | str | Unset = UNSET
    extra: CredentialProviderPatchExtraType0 | None | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        from ..models.credential_provider_patch_extra_type_0 import (
            CredentialProviderPatchExtraType0,
        )  # noqa: PLC0415

        name: None | str | Unset
        if isinstance(self.name, Unset):
            name = UNSET
        else:
            name = self.name

        authorize_url: None | str | Unset
        if isinstance(self.authorize_url, Unset):
            authorize_url = UNSET
        else:
            authorize_url = self.authorize_url

        token_url: None | str | Unset
        if isinstance(self.token_url, Unset):
            token_url = UNSET
        else:
            token_url = self.token_url

        client_id: None | str | Unset
        if isinstance(self.client_id, Unset):
            client_id = UNSET
        else:
            client_id = self.client_id

        status: None | str | Unset
        if isinstance(self.status, Unset):
            status = UNSET
        else:
            status = self.status

        extra: dict[str, Any] | None | Unset
        if isinstance(self.extra, Unset):
            extra = UNSET
        elif isinstance(self.extra, CredentialProviderPatchExtraType0):
            extra = self.extra.to_dict()
        else:
            extra = self.extra

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if name is not UNSET:
            field_dict["name"] = name
        if authorize_url is not UNSET:
            field_dict["authorizeUrl"] = authorize_url
        if token_url is not UNSET:
            field_dict["tokenUrl"] = token_url
        if client_id is not UNSET:
            field_dict["clientId"] = client_id
        if status is not UNSET:
            field_dict["status"] = status
        if extra is not UNSET:
            field_dict["extra"] = extra

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.credential_provider_patch_extra_type_0 import (
            CredentialProviderPatchExtraType0,
        )  # noqa: PLC0415

        d = dict(src_dict)

        def _parse_name(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        name = _parse_name(d.pop("name", UNSET))

        def _parse_authorize_url(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        authorize_url = _parse_authorize_url(d.pop("authorizeUrl", UNSET))

        def _parse_token_url(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        token_url = _parse_token_url(d.pop("tokenUrl", UNSET))

        def _parse_client_id(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        client_id = _parse_client_id(d.pop("clientId", UNSET))

        def _parse_status(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        status = _parse_status(d.pop("status", UNSET))

        def _parse_extra(data: object) -> CredentialProviderPatchExtraType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                extra_type_0 = CredentialProviderPatchExtraType0.from_dict(data)

                return extra_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(CredentialProviderPatchExtraType0 | None | Unset, data)

        extra = _parse_extra(d.pop("extra", UNSET))

        credential_provider_patch = cls(
            name=name,
            authorize_url=authorize_url,
            token_url=token_url,
            client_id=client_id,
            status=status,
            extra=extra,
        )

        return credential_provider_patch

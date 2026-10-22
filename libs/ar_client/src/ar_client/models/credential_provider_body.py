from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast

if TYPE_CHECKING:
    from ..models.credential_provider_body_extra_type_0 import CredentialProviderBodyExtraType0


T = TypeVar("T", bound="CredentialProviderBody")


@_attrs_define
class CredentialProviderBody:
    """
    Attributes:
        slug (str):
        name (str):
        kind (str | Unset):  Default: 'oauth2'.
        authorize_url (None | str | Unset):
        token_url (None | str | Unset):
        client_id (None | str | Unset):
        default_scopes (list[str] | Unset):
        token_exchange_audience (None | str | Unset):
        extra (CredentialProviderBodyExtraType0 | None | Unset):
    """

    slug: str
    name: str
    kind: str | Unset = "oauth2"
    authorize_url: None | str | Unset = UNSET
    token_url: None | str | Unset = UNSET
    client_id: None | str | Unset = UNSET
    default_scopes: list[str] | Unset = UNSET
    token_exchange_audience: None | str | Unset = UNSET
    extra: CredentialProviderBodyExtraType0 | None | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        from ..models.credential_provider_body_extra_type_0 import CredentialProviderBodyExtraType0  # noqa: PLC0415

        slug = self.slug

        name = self.name

        kind = self.kind

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

        default_scopes: list[str] | Unset = UNSET
        if not isinstance(self.default_scopes, Unset):
            default_scopes = self.default_scopes

        token_exchange_audience: None | str | Unset
        if isinstance(self.token_exchange_audience, Unset):
            token_exchange_audience = UNSET
        else:
            token_exchange_audience = self.token_exchange_audience

        extra: dict[str, Any] | None | Unset
        if isinstance(self.extra, Unset):
            extra = UNSET
        elif isinstance(self.extra, CredentialProviderBodyExtraType0):
            extra = self.extra.to_dict()
        else:
            extra = self.extra

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "slug": slug,
                "name": name,
            }
        )
        if kind is not UNSET:
            field_dict["kind"] = kind
        if authorize_url is not UNSET:
            field_dict["authorizeUrl"] = authorize_url
        if token_url is not UNSET:
            field_dict["tokenUrl"] = token_url
        if client_id is not UNSET:
            field_dict["clientId"] = client_id
        if default_scopes is not UNSET:
            field_dict["defaultScopes"] = default_scopes
        if token_exchange_audience is not UNSET:
            field_dict["tokenExchangeAudience"] = token_exchange_audience
        if extra is not UNSET:
            field_dict["extra"] = extra

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.credential_provider_body_extra_type_0 import CredentialProviderBodyExtraType0  # noqa: PLC0415

        d = dict(src_dict)
        slug = d.pop("slug")

        name = d.pop("name")

        kind = d.pop("kind", UNSET)

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

        default_scopes = cast(list[str], d.pop("defaultScopes", UNSET))

        def _parse_token_exchange_audience(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        token_exchange_audience = _parse_token_exchange_audience(
            d.pop("tokenExchangeAudience", UNSET)
        )

        def _parse_extra(data: object) -> CredentialProviderBodyExtraType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                extra_type_0 = CredentialProviderBodyExtraType0.from_dict(data)

                return extra_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(CredentialProviderBodyExtraType0 | None | Unset, data)

        extra = _parse_extra(d.pop("extra", UNSET))

        credential_provider_body = cls(
            slug=slug,
            name=name,
            kind=kind,
            authorize_url=authorize_url,
            token_url=token_url,
            client_id=client_id,
            default_scopes=default_scopes,
            token_exchange_audience=token_exchange_audience,
            extra=extra,
        )

        return credential_provider_body

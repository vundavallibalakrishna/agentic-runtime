from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast


T = TypeVar("T", bound="ServiceConnectionBody")


@_attrs_define
class ServiceConnectionBody:
    """
    Attributes:
        name (str):
        kind (str):
        secret (str | Unset):  Default: ''.
        header_name (str | Unset):  Default: 'X-API-Key'.
        username (str | Unset):  Default: ''.
        token_url (str | Unset):  Default: ''.
        authorize_url (str | Unset):  Default: ''.
        client_id (str | Unset):  Default: ''.
        scopes (list[str] | Unset):
        probe_url (str | Unset):  Default: ''.
        expires_at (str | Unset):  Default: ''.
    """

    name: str
    kind: str
    secret: str | Unset = ""
    header_name: str | Unset = "X-API-Key"
    username: str | Unset = ""
    token_url: str | Unset = ""
    authorize_url: str | Unset = ""
    client_id: str | Unset = ""
    scopes: list[str] | Unset = UNSET
    probe_url: str | Unset = ""
    expires_at: str | Unset = ""

    def to_dict(self) -> dict[str, Any]:
        name = self.name

        kind = self.kind

        secret = self.secret

        header_name = self.header_name

        username = self.username

        token_url = self.token_url

        authorize_url = self.authorize_url

        client_id = self.client_id

        scopes: list[str] | Unset = UNSET
        if not isinstance(self.scopes, Unset):
            scopes = self.scopes

        probe_url = self.probe_url

        expires_at = self.expires_at

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "name": name,
                "kind": kind,
            }
        )
        if secret is not UNSET:
            field_dict["secret"] = secret
        if header_name is not UNSET:
            field_dict["headerName"] = header_name
        if username is not UNSET:
            field_dict["username"] = username
        if token_url is not UNSET:
            field_dict["tokenUrl"] = token_url
        if authorize_url is not UNSET:
            field_dict["authorizeUrl"] = authorize_url
        if client_id is not UNSET:
            field_dict["clientId"] = client_id
        if scopes is not UNSET:
            field_dict["scopes"] = scopes
        if probe_url is not UNSET:
            field_dict["probeUrl"] = probe_url
        if expires_at is not UNSET:
            field_dict["expiresAt"] = expires_at

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        name = d.pop("name")

        kind = d.pop("kind")

        secret = d.pop("secret", UNSET)

        header_name = d.pop("headerName", UNSET)

        username = d.pop("username", UNSET)

        token_url = d.pop("tokenUrl", UNSET)

        authorize_url = d.pop("authorizeUrl", UNSET)

        client_id = d.pop("clientId", UNSET)

        scopes = cast(list[str], d.pop("scopes", UNSET))

        probe_url = d.pop("probeUrl", UNSET)

        expires_at = d.pop("expiresAt", UNSET)

        service_connection_body = cls(
            name=name,
            kind=kind,
            secret=secret,
            header_name=header_name,
            username=username,
            token_url=token_url,
            authorize_url=authorize_url,
            client_id=client_id,
            scopes=scopes,
            probe_url=probe_url,
            expires_at=expires_at,
        )

        return service_connection_body

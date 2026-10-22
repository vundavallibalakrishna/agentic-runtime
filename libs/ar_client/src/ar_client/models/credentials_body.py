from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast


T = TypeVar("T", bound="CredentialsBody")


@_attrs_define
class CredentialsBody:
    """
    Attributes:
        bot_token (None | str | Unset):
        signing_secret (None | str | Unset):
        app_token (None | str | Unset):
        app_id (None | str | Unset):
        app_password (None | str | Unset):
        tenant_id (None | str | Unset):
        imap_host (None | str | Unset):
        imap_port (int | None | Unset):
        smtp_host (None | str | Unset):
        smtp_port (int | None | Unset):
        username (None | str | Unset):
        password (None | str | Unset):
        address (None | str | Unset):
        widget_secret (None | str | Unset):
        secret (None | str | Unset):
    """

    bot_token: None | str | Unset = UNSET
    signing_secret: None | str | Unset = UNSET
    app_token: None | str | Unset = UNSET
    app_id: None | str | Unset = UNSET
    app_password: None | str | Unset = UNSET
    tenant_id: None | str | Unset = UNSET
    imap_host: None | str | Unset = UNSET
    imap_port: int | None | Unset = UNSET
    smtp_host: None | str | Unset = UNSET
    smtp_port: int | None | Unset = UNSET
    username: None | str | Unset = UNSET
    password: None | str | Unset = UNSET
    address: None | str | Unset = UNSET
    widget_secret: None | str | Unset = UNSET
    secret: None | str | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        bot_token: None | str | Unset
        if isinstance(self.bot_token, Unset):
            bot_token = UNSET
        else:
            bot_token = self.bot_token

        signing_secret: None | str | Unset
        if isinstance(self.signing_secret, Unset):
            signing_secret = UNSET
        else:
            signing_secret = self.signing_secret

        app_token: None | str | Unset
        if isinstance(self.app_token, Unset):
            app_token = UNSET
        else:
            app_token = self.app_token

        app_id: None | str | Unset
        if isinstance(self.app_id, Unset):
            app_id = UNSET
        else:
            app_id = self.app_id

        app_password: None | str | Unset
        if isinstance(self.app_password, Unset):
            app_password = UNSET
        else:
            app_password = self.app_password

        tenant_id: None | str | Unset
        if isinstance(self.tenant_id, Unset):
            tenant_id = UNSET
        else:
            tenant_id = self.tenant_id

        imap_host: None | str | Unset
        if isinstance(self.imap_host, Unset):
            imap_host = UNSET
        else:
            imap_host = self.imap_host

        imap_port: int | None | Unset
        if isinstance(self.imap_port, Unset):
            imap_port = UNSET
        else:
            imap_port = self.imap_port

        smtp_host: None | str | Unset
        if isinstance(self.smtp_host, Unset):
            smtp_host = UNSET
        else:
            smtp_host = self.smtp_host

        smtp_port: int | None | Unset
        if isinstance(self.smtp_port, Unset):
            smtp_port = UNSET
        else:
            smtp_port = self.smtp_port

        username: None | str | Unset
        if isinstance(self.username, Unset):
            username = UNSET
        else:
            username = self.username

        password: None | str | Unset
        if isinstance(self.password, Unset):
            password = UNSET
        else:
            password = self.password

        address: None | str | Unset
        if isinstance(self.address, Unset):
            address = UNSET
        else:
            address = self.address

        widget_secret: None | str | Unset
        if isinstance(self.widget_secret, Unset):
            widget_secret = UNSET
        else:
            widget_secret = self.widget_secret

        secret: None | str | Unset
        if isinstance(self.secret, Unset):
            secret = UNSET
        else:
            secret = self.secret

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if bot_token is not UNSET:
            field_dict["botToken"] = bot_token
        if signing_secret is not UNSET:
            field_dict["signingSecret"] = signing_secret
        if app_token is not UNSET:
            field_dict["appToken"] = app_token
        if app_id is not UNSET:
            field_dict["appId"] = app_id
        if app_password is not UNSET:
            field_dict["appPassword"] = app_password
        if tenant_id is not UNSET:
            field_dict["tenantId"] = tenant_id
        if imap_host is not UNSET:
            field_dict["imapHost"] = imap_host
        if imap_port is not UNSET:
            field_dict["imapPort"] = imap_port
        if smtp_host is not UNSET:
            field_dict["smtpHost"] = smtp_host
        if smtp_port is not UNSET:
            field_dict["smtpPort"] = smtp_port
        if username is not UNSET:
            field_dict["username"] = username
        if password is not UNSET:
            field_dict["password"] = password
        if address is not UNSET:
            field_dict["address"] = address
        if widget_secret is not UNSET:
            field_dict["widgetSecret"] = widget_secret
        if secret is not UNSET:
            field_dict["secret"] = secret

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)

        def _parse_bot_token(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        bot_token = _parse_bot_token(d.pop("botToken", UNSET))

        def _parse_signing_secret(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        signing_secret = _parse_signing_secret(d.pop("signingSecret", UNSET))

        def _parse_app_token(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        app_token = _parse_app_token(d.pop("appToken", UNSET))

        def _parse_app_id(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        app_id = _parse_app_id(d.pop("appId", UNSET))

        def _parse_app_password(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        app_password = _parse_app_password(d.pop("appPassword", UNSET))

        def _parse_tenant_id(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        tenant_id = _parse_tenant_id(d.pop("tenantId", UNSET))

        def _parse_imap_host(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        imap_host = _parse_imap_host(d.pop("imapHost", UNSET))

        def _parse_imap_port(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        imap_port = _parse_imap_port(d.pop("imapPort", UNSET))

        def _parse_smtp_host(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        smtp_host = _parse_smtp_host(d.pop("smtpHost", UNSET))

        def _parse_smtp_port(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        smtp_port = _parse_smtp_port(d.pop("smtpPort", UNSET))

        def _parse_username(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        username = _parse_username(d.pop("username", UNSET))

        def _parse_password(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        password = _parse_password(d.pop("password", UNSET))

        def _parse_address(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        address = _parse_address(d.pop("address", UNSET))

        def _parse_widget_secret(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        widget_secret = _parse_widget_secret(d.pop("widgetSecret", UNSET))

        def _parse_secret(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        secret = _parse_secret(d.pop("secret", UNSET))

        credentials_body = cls(
            bot_token=bot_token,
            signing_secret=signing_secret,
            app_token=app_token,
            app_id=app_id,
            app_password=app_password,
            tenant_id=tenant_id,
            imap_host=imap_host,
            imap_port=imap_port,
            smtp_host=smtp_host,
            smtp_port=smtp_port,
            username=username,
            password=password,
            address=address,
            widget_secret=widget_secret,
            secret=secret,
        )

        return credentials_body

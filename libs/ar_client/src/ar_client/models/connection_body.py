from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast

if TYPE_CHECKING:
    from ..models.connection_body_allowlist_type_0 import ConnectionBodyAllowlistType0


T = TypeVar("T", bound="ConnectionBody")


@_attrs_define
class ConnectionBody:
    """
    Attributes:
        name (str):
        engine (str | Unset):  Default: 'postgres'.
        dsn (str | Unset):  Default: 'memory://warehouse'.
        identity_mode (str | Unset):  Default: 'service'.
        allowlist (ConnectionBodyAllowlistType0 | None | Unset):
        row_limit (int | Unset):  Default: 1000.
        statement_timeout_s (int | Unset):  Default: 30.
        classification (str | Unset):  Default: 'internal'.
        schema_notes (str | Unset):  Default: ''.
    """

    name: str
    engine: str | Unset = "postgres"
    dsn: str | Unset = "memory://warehouse"
    identity_mode: str | Unset = "service"
    allowlist: ConnectionBodyAllowlistType0 | None | Unset = UNSET
    row_limit: int | Unset = 1000
    statement_timeout_s: int | Unset = 30
    classification: str | Unset = "internal"
    schema_notes: str | Unset = ""

    def to_dict(self) -> dict[str, Any]:
        from ..models.connection_body_allowlist_type_0 import ConnectionBodyAllowlistType0  # noqa: PLC0415

        name = self.name

        engine = self.engine

        dsn = self.dsn

        identity_mode = self.identity_mode

        allowlist: dict[str, Any] | None | Unset
        if isinstance(self.allowlist, Unset):
            allowlist = UNSET
        elif isinstance(self.allowlist, ConnectionBodyAllowlistType0):
            allowlist = self.allowlist.to_dict()
        else:
            allowlist = self.allowlist

        row_limit = self.row_limit

        statement_timeout_s = self.statement_timeout_s

        classification = self.classification

        schema_notes = self.schema_notes

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "name": name,
            }
        )
        if engine is not UNSET:
            field_dict["engine"] = engine
        if dsn is not UNSET:
            field_dict["dsn"] = dsn
        if identity_mode is not UNSET:
            field_dict["identityMode"] = identity_mode
        if allowlist is not UNSET:
            field_dict["allowlist"] = allowlist
        if row_limit is not UNSET:
            field_dict["rowLimit"] = row_limit
        if statement_timeout_s is not UNSET:
            field_dict["statementTimeoutS"] = statement_timeout_s
        if classification is not UNSET:
            field_dict["classification"] = classification
        if schema_notes is not UNSET:
            field_dict["schemaNotes"] = schema_notes

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.connection_body_allowlist_type_0 import ConnectionBodyAllowlistType0  # noqa: PLC0415

        d = dict(src_dict)
        name = d.pop("name")

        engine = d.pop("engine", UNSET)

        dsn = d.pop("dsn", UNSET)

        identity_mode = d.pop("identityMode", UNSET)

        def _parse_allowlist(data: object) -> ConnectionBodyAllowlistType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                allowlist_type_0 = ConnectionBodyAllowlistType0.from_dict(data)

                return allowlist_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(ConnectionBodyAllowlistType0 | None | Unset, data)

        allowlist = _parse_allowlist(d.pop("allowlist", UNSET))

        row_limit = d.pop("rowLimit", UNSET)

        statement_timeout_s = d.pop("statementTimeoutS", UNSET)

        classification = d.pop("classification", UNSET)

        schema_notes = d.pop("schemaNotes", UNSET)

        connection_body = cls(
            name=name,
            engine=engine,
            dsn=dsn,
            identity_mode=identity_mode,
            allowlist=allowlist,
            row_limit=row_limit,
            statement_timeout_s=statement_timeout_s,
            classification=classification,
            schema_notes=schema_notes,
        )

        return connection_body

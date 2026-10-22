from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast

if TYPE_CHECKING:
    from ..models.connection_patch_allowlist_type_0 import ConnectionPatchAllowlistType0


T = TypeVar("T", bound="ConnectionPatch")


@_attrs_define
class ConnectionPatch:
    """
    Attributes:
        name (None | str | Unset):
        schema_notes (None | str | Unset):
        classification (None | str | Unset):
        status (None | str | Unset):
        row_limit (int | None | Unset):
        identity_mode (None | str | Unset):
        allowlist (ConnectionPatchAllowlistType0 | None | Unset):
    """

    name: None | str | Unset = UNSET
    schema_notes: None | str | Unset = UNSET
    classification: None | str | Unset = UNSET
    status: None | str | Unset = UNSET
    row_limit: int | None | Unset = UNSET
    identity_mode: None | str | Unset = UNSET
    allowlist: ConnectionPatchAllowlistType0 | None | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        from ..models.connection_patch_allowlist_type_0 import ConnectionPatchAllowlistType0  # noqa: PLC0415

        name: None | str | Unset
        if isinstance(self.name, Unset):
            name = UNSET
        else:
            name = self.name

        schema_notes: None | str | Unset
        if isinstance(self.schema_notes, Unset):
            schema_notes = UNSET
        else:
            schema_notes = self.schema_notes

        classification: None | str | Unset
        if isinstance(self.classification, Unset):
            classification = UNSET
        else:
            classification = self.classification

        status: None | str | Unset
        if isinstance(self.status, Unset):
            status = UNSET
        else:
            status = self.status

        row_limit: int | None | Unset
        if isinstance(self.row_limit, Unset):
            row_limit = UNSET
        else:
            row_limit = self.row_limit

        identity_mode: None | str | Unset
        if isinstance(self.identity_mode, Unset):
            identity_mode = UNSET
        else:
            identity_mode = self.identity_mode

        allowlist: dict[str, Any] | None | Unset
        if isinstance(self.allowlist, Unset):
            allowlist = UNSET
        elif isinstance(self.allowlist, ConnectionPatchAllowlistType0):
            allowlist = self.allowlist.to_dict()
        else:
            allowlist = self.allowlist

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if name is not UNSET:
            field_dict["name"] = name
        if schema_notes is not UNSET:
            field_dict["schemaNotes"] = schema_notes
        if classification is not UNSET:
            field_dict["classification"] = classification
        if status is not UNSET:
            field_dict["status"] = status
        if row_limit is not UNSET:
            field_dict["rowLimit"] = row_limit
        if identity_mode is not UNSET:
            field_dict["identityMode"] = identity_mode
        if allowlist is not UNSET:
            field_dict["allowlist"] = allowlist

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.connection_patch_allowlist_type_0 import ConnectionPatchAllowlistType0  # noqa: PLC0415

        d = dict(src_dict)

        def _parse_name(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        name = _parse_name(d.pop("name", UNSET))

        def _parse_schema_notes(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        schema_notes = _parse_schema_notes(d.pop("schemaNotes", UNSET))

        def _parse_classification(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        classification = _parse_classification(d.pop("classification", UNSET))

        def _parse_status(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        status = _parse_status(d.pop("status", UNSET))

        def _parse_row_limit(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        row_limit = _parse_row_limit(d.pop("rowLimit", UNSET))

        def _parse_identity_mode(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        identity_mode = _parse_identity_mode(d.pop("identityMode", UNSET))

        def _parse_allowlist(data: object) -> ConnectionPatchAllowlistType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                allowlist_type_0 = ConnectionPatchAllowlistType0.from_dict(data)

                return allowlist_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(ConnectionPatchAllowlistType0 | None | Unset, data)

        allowlist = _parse_allowlist(d.pop("allowlist", UNSET))

        connection_patch = cls(
            name=name,
            schema_notes=schema_notes,
            classification=classification,
            status=status,
            row_limit=row_limit,
            identity_mode=identity_mode,
            allowlist=allowlist,
        )

        return connection_patch

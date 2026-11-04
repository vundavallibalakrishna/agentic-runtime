from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast
from uuid import UUID


T = TypeVar("T", bound="MemberBody")


@_attrs_define
class MemberBody:
    """
    Attributes:
        kind (str | Unset):  Default: ''.
        library_document_id (None | Unset | UUID):
        url (str | Unset):  Default: ''.
        connection_id (None | Unset | UUID):
        path (str | Unset):  Default: ''.
        title (str | Unset):  Default: ''.
        text (str | Unset):  Default: ''.
        external_id (str | Unset):  Default: ''.
        force (bool | Unset):  Default: False.
    """

    kind: str | Unset = ""
    library_document_id: None | Unset | UUID = UNSET
    url: str | Unset = ""
    connection_id: None | Unset | UUID = UNSET
    path: str | Unset = ""
    title: str | Unset = ""
    text: str | Unset = ""
    external_id: str | Unset = ""
    force: bool | Unset = False

    def to_dict(self) -> dict[str, Any]:
        kind = self.kind

        library_document_id: None | str | Unset
        if isinstance(self.library_document_id, Unset):
            library_document_id = UNSET
        elif isinstance(self.library_document_id, UUID):
            library_document_id = str(self.library_document_id)
        else:
            library_document_id = self.library_document_id

        url = self.url

        connection_id: None | str | Unset
        if isinstance(self.connection_id, Unset):
            connection_id = UNSET
        elif isinstance(self.connection_id, UUID):
            connection_id = str(self.connection_id)
        else:
            connection_id = self.connection_id

        path = self.path

        title = self.title

        text = self.text

        external_id = self.external_id

        force = self.force

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if kind is not UNSET:
            field_dict["kind"] = kind
        if library_document_id is not UNSET:
            field_dict["libraryDocumentId"] = library_document_id
        if url is not UNSET:
            field_dict["url"] = url
        if connection_id is not UNSET:
            field_dict["connectionId"] = connection_id
        if path is not UNSET:
            field_dict["path"] = path
        if title is not UNSET:
            field_dict["title"] = title
        if text is not UNSET:
            field_dict["text"] = text
        if external_id is not UNSET:
            field_dict["externalId"] = external_id
        if force is not UNSET:
            field_dict["force"] = force

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        kind = d.pop("kind", UNSET)

        def _parse_library_document_id(data: object) -> None | Unset | UUID:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                library_document_id_type_0 = UUID(data)

                return library_document_id_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(None | Unset | UUID, data)

        library_document_id = _parse_library_document_id(d.pop("libraryDocumentId", UNSET))

        url = d.pop("url", UNSET)

        def _parse_connection_id(data: object) -> None | Unset | UUID:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                connection_id_type_0 = UUID(data)

                return connection_id_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(None | Unset | UUID, data)

        connection_id = _parse_connection_id(d.pop("connectionId", UNSET))

        path = d.pop("path", UNSET)

        title = d.pop("title", UNSET)

        text = d.pop("text", UNSET)

        external_id = d.pop("externalId", UNSET)

        force = d.pop("force", UNSET)

        member_body = cls(
            kind=kind,
            library_document_id=library_document_id,
            url=url,
            connection_id=connection_id,
            path=path,
            title=title,
            text=text,
            external_id=external_id,
            force=force,
        )

        return member_body

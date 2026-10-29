from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast

if TYPE_CHECKING:
    from ..models.open_api_import_document_type_0 import OpenApiImportDocumentType0


T = TypeVar("T", bound="OpenApiImport")


@_attrs_define
class OpenApiImport:
    """
    Attributes:
        slug (str):
        name (str | Unset):  Default: ''.
        description (str | Unset):  Default: ''.
        document (None | OpenApiImportDocumentType0 | str | Unset):
        url (str | Unset):  Default: ''.
        base_url (str | Unset):  Default: ''.
        operations (list[str] | Unset):
        connection (str | Unset):  Default: ''.
    """

    slug: str
    name: str | Unset = ""
    description: str | Unset = ""
    document: None | OpenApiImportDocumentType0 | str | Unset = UNSET
    url: str | Unset = ""
    base_url: str | Unset = ""
    operations: list[str] | Unset = UNSET
    connection: str | Unset = ""

    def to_dict(self) -> dict[str, Any]:
        from ..models.open_api_import_document_type_0 import OpenApiImportDocumentType0  # noqa: PLC0415

        slug = self.slug

        name = self.name

        description = self.description

        document: dict[str, Any] | None | str | Unset
        if isinstance(self.document, Unset):
            document = UNSET
        elif isinstance(self.document, OpenApiImportDocumentType0):
            document = self.document.to_dict()
        else:
            document = self.document

        url = self.url

        base_url = self.base_url

        operations: list[str] | Unset = UNSET
        if not isinstance(self.operations, Unset):
            operations = self.operations

        connection = self.connection

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "slug": slug,
            }
        )
        if name is not UNSET:
            field_dict["name"] = name
        if description is not UNSET:
            field_dict["description"] = description
        if document is not UNSET:
            field_dict["document"] = document
        if url is not UNSET:
            field_dict["url"] = url
        if base_url is not UNSET:
            field_dict["baseUrl"] = base_url
        if operations is not UNSET:
            field_dict["operations"] = operations
        if connection is not UNSET:
            field_dict["connection"] = connection

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.open_api_import_document_type_0 import OpenApiImportDocumentType0  # noqa: PLC0415

        d = dict(src_dict)
        slug = d.pop("slug")

        name = d.pop("name", UNSET)

        description = d.pop("description", UNSET)

        def _parse_document(data: object) -> None | OpenApiImportDocumentType0 | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                document_type_0 = OpenApiImportDocumentType0.from_dict(data)

                return document_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(None | OpenApiImportDocumentType0 | str | Unset, data)

        document = _parse_document(d.pop("document", UNSET))

        url = d.pop("url", UNSET)

        base_url = d.pop("baseUrl", UNSET)

        operations = cast(list[str], d.pop("operations", UNSET))

        connection = d.pop("connection", UNSET)

        open_api_import = cls(
            slug=slug,
            name=name,
            description=description,
            document=document,
            url=url,
            base_url=base_url,
            operations=operations,
            connection=connection,
        )

        return open_api_import

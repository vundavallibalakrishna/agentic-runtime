from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast

if TYPE_CHECKING:
    from ..models.open_api_preview_document_type_0 import OpenApiPreviewDocumentType0


T = TypeVar("T", bound="OpenApiPreview")


@_attrs_define
class OpenApiPreview:
    """
    Attributes:
        document (None | OpenApiPreviewDocumentType0 | str | Unset):
        url (str | Unset):  Default: ''.
        base_url (str | Unset):  Default: ''.
    """

    document: None | OpenApiPreviewDocumentType0 | str | Unset = UNSET
    url: str | Unset = ""
    base_url: str | Unset = ""

    def to_dict(self) -> dict[str, Any]:
        from ..models.open_api_preview_document_type_0 import OpenApiPreviewDocumentType0  # noqa: PLC0415

        document: dict[str, Any] | None | str | Unset
        if isinstance(self.document, Unset):
            document = UNSET
        elif isinstance(self.document, OpenApiPreviewDocumentType0):
            document = self.document.to_dict()
        else:
            document = self.document

        url = self.url

        base_url = self.base_url

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if document is not UNSET:
            field_dict["document"] = document
        if url is not UNSET:
            field_dict["url"] = url
        if base_url is not UNSET:
            field_dict["baseUrl"] = base_url

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.open_api_preview_document_type_0 import OpenApiPreviewDocumentType0  # noqa: PLC0415

        d = dict(src_dict)

        def _parse_document(data: object) -> None | OpenApiPreviewDocumentType0 | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                document_type_0 = OpenApiPreviewDocumentType0.from_dict(data)

                return document_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(None | OpenApiPreviewDocumentType0 | str | Unset, data)

        document = _parse_document(d.pop("document", UNSET))

        url = d.pop("url", UNSET)

        base_url = d.pop("baseUrl", UNSET)

        open_api_preview = cls(
            document=document,
            url=url,
            base_url=base_url,
        )

        return open_api_preview

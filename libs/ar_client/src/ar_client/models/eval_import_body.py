from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast
from uuid import UUID


T = TypeVar("T", bound="EvalImportBody")


@_attrs_define
class EvalImportBody:
    """A stored eval dataset file, or the dataset's text itself. Exactly one.

    Attributes:
        file_id (None | Unset | UUID):
        content (None | str | Unset):
    """

    file_id: None | Unset | UUID = UNSET
    content: None | str | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        file_id: None | str | Unset
        if isinstance(self.file_id, Unset):
            file_id = UNSET
        elif isinstance(self.file_id, UUID):
            file_id = str(self.file_id)
        else:
            file_id = self.file_id

        content: None | str | Unset
        if isinstance(self.content, Unset):
            content = UNSET
        else:
            content = self.content

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if file_id is not UNSET:
            field_dict["fileId"] = file_id
        if content is not UNSET:
            field_dict["content"] = content

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)

        def _parse_file_id(data: object) -> None | Unset | UUID:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                file_id_type_0 = UUID(data)

                return file_id_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(None | Unset | UUID, data)

        file_id = _parse_file_id(d.pop("fileId", UNSET))

        def _parse_content(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        content = _parse_content(d.pop("content", UNSET))

        eval_import_body = cls(
            file_id=file_id,
            content=content,
        )

        return eval_import_body

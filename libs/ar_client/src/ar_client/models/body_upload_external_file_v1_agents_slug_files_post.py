from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field
import json
from .. import types

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast
from uuid import UUID


T = TypeVar("T", bound="BodyUploadExternalFileV1AgentsSlugFilesPost")


@_attrs_define
class BodyUploadExternalFileV1AgentsSlugFilesPost:
    """
    Attributes:
        upload (str):
        mime_type (str | Unset):  Default: ''.
        expires_after_seconds (int | None | Unset):
        replaces_file_id (None | Unset | UUID):
    """

    upload: str
    mime_type: str | Unset = ""
    expires_after_seconds: int | None | Unset = UNSET
    replaces_file_id: None | Unset | UUID = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        upload = self.upload

        mime_type = self.mime_type

        expires_after_seconds: int | None | Unset
        if isinstance(self.expires_after_seconds, Unset):
            expires_after_seconds = UNSET
        else:
            expires_after_seconds = self.expires_after_seconds

        replaces_file_id: None | str | Unset
        if isinstance(self.replaces_file_id, Unset):
            replaces_file_id = UNSET
        elif isinstance(self.replaces_file_id, UUID):
            replaces_file_id = str(self.replaces_file_id)
        else:
            replaces_file_id = self.replaces_file_id

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "upload": upload,
            }
        )
        if mime_type is not UNSET:
            field_dict["mime_type"] = mime_type
        if expires_after_seconds is not UNSET:
            field_dict["expires_after_seconds"] = expires_after_seconds
        if replaces_file_id is not UNSET:
            field_dict["replaces_file_id"] = replaces_file_id

        return field_dict

    def to_multipart(self) -> types.RequestFiles:
        files: types.RequestFiles = []

        files.append(("upload", (None, str(self.upload).encode(), "text/plain")))

        if not isinstance(self.mime_type, Unset):
            files.append(("mime_type", (None, str(self.mime_type).encode(), "text/plain")))

        if not isinstance(self.expires_after_seconds, Unset):
            if isinstance(self.expires_after_seconds, int):
                files.append(
                    (
                        "expires_after_seconds",
                        (None, str(self.expires_after_seconds).encode(), "text/plain"),
                    )
                )
            else:
                files.append(
                    (
                        "expires_after_seconds",
                        (None, str(self.expires_after_seconds).encode(), "text/plain"),
                    )
                )

        if not isinstance(self.replaces_file_id, Unset):
            if isinstance(self.replaces_file_id, UUID):
                files.append(("replaces_file_id", (None, str(self.replaces_file_id), "text/plain")))
            else:
                files.append(
                    ("replaces_file_id", (None, str(self.replaces_file_id).encode(), "text/plain"))
                )

        for prop_name, prop in self.additional_properties.items():
            files.append((prop_name, (None, str(prop).encode(), "text/plain")))

        return files

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        upload = d.pop("upload")

        mime_type = d.pop("mime_type", UNSET)

        def _parse_expires_after_seconds(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        expires_after_seconds = _parse_expires_after_seconds(d.pop("expires_after_seconds", UNSET))

        def _parse_replaces_file_id(data: object) -> None | Unset | UUID:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                replaces_file_id_type_0 = UUID(data)

                return replaces_file_id_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(None | Unset | UUID, data)

        replaces_file_id = _parse_replaces_file_id(d.pop("replaces_file_id", UNSET))

        body_upload_external_file_v1_agents_slug_files_post = cls(
            upload=upload,
            mime_type=mime_type,
            expires_after_seconds=expires_after_seconds,
            replaces_file_id=replaces_file_id,
        )

        body_upload_external_file_v1_agents_slug_files_post.additional_properties = d
        return body_upload_external_file_v1_agents_slug_files_post

    @property
    def additional_keys(self) -> list[str]:
        return list(self.additional_properties.keys())

    def __getitem__(self, key: str) -> Any:
        return self.additional_properties[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.additional_properties[key] = value

    def __delitem__(self, key: str) -> None:
        del self.additional_properties[key]

    def __contains__(self, key: str) -> bool:
        return key in self.additional_properties

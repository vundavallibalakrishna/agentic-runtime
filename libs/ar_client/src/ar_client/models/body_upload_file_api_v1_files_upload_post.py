from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field
import json
from .. import types

from ..types import UNSET, Unset

from ..types import UNSET, Unset






T = TypeVar("T", bound="BodyUploadFileApiV1FilesUploadPost")



@_attrs_define
class BodyUploadFileApiV1FilesUploadPost:
    """ 
        Attributes:
            upload (str):
            mime_type (str | Unset):  Default: ''.
     """

    upload: str
    mime_type: str | Unset = ''
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)





    def to_dict(self) -> dict[str, Any]:
        upload = self.upload

        mime_type = self.mime_type


        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({
            "upload": upload,
        })
        if mime_type is not UNSET:
            field_dict["mime_type"] = mime_type

        return field_dict


    def to_multipart(self) -> types.RequestFiles:
        files: types.RequestFiles = []

        files.append(("upload", (None, str(self.upload).encode(), "text/plain")))



        if not isinstance(self.mime_type, Unset):
            files.append(("mime_type", (None, str(self.mime_type).encode(), "text/plain")))




        for prop_name, prop in self.additional_properties.items():
            files.append((prop_name, (None, str(prop).encode(), "text/plain")))



        return files


    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        upload = d.pop("upload")

        mime_type = d.pop("mime_type", UNSET)

        body_upload_file_api_v1_files_upload_post = cls(
            upload=upload,
            mime_type=mime_type,
        )


        body_upload_file_api_v1_files_upload_post.additional_properties = d
        return body_upload_file_api_v1_files_upload_post

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

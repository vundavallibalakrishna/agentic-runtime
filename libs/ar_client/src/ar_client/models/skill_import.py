from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset


T = TypeVar("T", bound="SkillImport")


@_attrs_define
class SkillImport:
    """
    Attributes:
        markdown (str | Unset):  Default: ''.
        archive_b64 (str | Unset):  Default: ''.
    """

    markdown: str | Unset = ""
    archive_b64: str | Unset = ""

    def to_dict(self) -> dict[str, Any]:
        markdown = self.markdown

        archive_b64 = self.archive_b64

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if markdown is not UNSET:
            field_dict["markdown"] = markdown
        if archive_b64 is not UNSET:
            field_dict["archiveB64"] = archive_b64

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        markdown = d.pop("markdown", UNSET)

        archive_b64 = d.pop("archiveB64", UNSET)

        skill_import = cls(
            markdown=markdown,
            archive_b64=archive_b64,
        )

        return skill_import

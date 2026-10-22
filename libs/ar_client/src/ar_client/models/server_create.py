from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast

if TYPE_CHECKING:
    from ..models.version_body import VersionBody


T = TypeVar("T", bound="ServerCreate")


@_attrs_define
class ServerCreate:
    """
    Attributes:
        slug (str):
        name (str):
        version (VersionBody):
        description (str | Unset):  Default: ''.
        kind (str | Unset):  Default: 'remote_mcp'.
    """

    slug: str
    name: str
    version: VersionBody
    description: str | Unset = ""
    kind: str | Unset = "remote_mcp"

    def to_dict(self) -> dict[str, Any]:
        from ..models.version_body import VersionBody  # noqa: PLC0415

        slug = self.slug

        name = self.name

        version = self.version.to_dict()

        description = self.description

        kind = self.kind

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "slug": slug,
                "name": name,
                "version": version,
            }
        )
        if description is not UNSET:
            field_dict["description"] = description
        if kind is not UNSET:
            field_dict["kind"] = kind

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.version_body import VersionBody  # noqa: PLC0415

        d = dict(src_dict)
        slug = d.pop("slug")

        name = d.pop("name")

        version = VersionBody.from_dict(d.pop("version"))

        description = d.pop("description", UNSET)

        kind = d.pop("kind", UNSET)

        server_create = cls(
            slug=slug,
            name=name,
            version=version,
            description=description,
            kind=kind,
        )

        return server_create

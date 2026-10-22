from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast
from uuid import UUID

if TYPE_CHECKING:
    from ..models.collection_body_chunking_type_0 import CollectionBodyChunkingType0


T = TypeVar("T", bound="CollectionBody")


@_attrs_define
class CollectionBody:
    """
    Attributes:
        slug (str | Unset):  Default: ''.
        name (str | Unset):  Default: ''.
        description (str | Unset):  Default: ''.
        visibility (str | Unset):  Default: 'tenant'.
        owner_team_id (None | Unset | UUID):
        acl_mode (str | Unset):  Default: 'source'.
        sensitivity (str | Unset):  Default: 'normal'.
        classification (str | Unset):  Default: 'internal'.
        embedding_alias (str | Unset):  Default: 'embed'.
        text_search_config (str | Unset):  Default: 'simple'.
        chunking (CollectionBodyChunkingType0 | None | Unset):
        dims (int | Unset):  Default: 1024.
    """

    slug: str | Unset = ""
    name: str | Unset = ""
    description: str | Unset = ""
    visibility: str | Unset = "tenant"
    owner_team_id: None | Unset | UUID = UNSET
    acl_mode: str | Unset = "source"
    sensitivity: str | Unset = "normal"
    classification: str | Unset = "internal"
    embedding_alias: str | Unset = "embed"
    text_search_config: str | Unset = "simple"
    chunking: CollectionBodyChunkingType0 | None | Unset = UNSET
    dims: int | Unset = 1024

    def to_dict(self) -> dict[str, Any]:
        from ..models.collection_body_chunking_type_0 import CollectionBodyChunkingType0  # noqa: PLC0415

        slug = self.slug

        name = self.name

        description = self.description

        visibility = self.visibility

        owner_team_id: None | str | Unset
        if isinstance(self.owner_team_id, Unset):
            owner_team_id = UNSET
        elif isinstance(self.owner_team_id, UUID):
            owner_team_id = str(self.owner_team_id)
        else:
            owner_team_id = self.owner_team_id

        acl_mode = self.acl_mode

        sensitivity = self.sensitivity

        classification = self.classification

        embedding_alias = self.embedding_alias

        text_search_config = self.text_search_config

        chunking: dict[str, Any] | None | Unset
        if isinstance(self.chunking, Unset):
            chunking = UNSET
        elif isinstance(self.chunking, CollectionBodyChunkingType0):
            chunking = self.chunking.to_dict()
        else:
            chunking = self.chunking

        dims = self.dims

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if slug is not UNSET:
            field_dict["slug"] = slug
        if name is not UNSET:
            field_dict["name"] = name
        if description is not UNSET:
            field_dict["description"] = description
        if visibility is not UNSET:
            field_dict["visibility"] = visibility
        if owner_team_id is not UNSET:
            field_dict["ownerTeamId"] = owner_team_id
        if acl_mode is not UNSET:
            field_dict["aclMode"] = acl_mode
        if sensitivity is not UNSET:
            field_dict["sensitivity"] = sensitivity
        if classification is not UNSET:
            field_dict["classification"] = classification
        if embedding_alias is not UNSET:
            field_dict["embeddingAlias"] = embedding_alias
        if text_search_config is not UNSET:
            field_dict["textSearchConfig"] = text_search_config
        if chunking is not UNSET:
            field_dict["chunking"] = chunking
        if dims is not UNSET:
            field_dict["dims"] = dims

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.collection_body_chunking_type_0 import CollectionBodyChunkingType0  # noqa: PLC0415

        d = dict(src_dict)
        slug = d.pop("slug", UNSET)

        name = d.pop("name", UNSET)

        description = d.pop("description", UNSET)

        visibility = d.pop("visibility", UNSET)

        def _parse_owner_team_id(data: object) -> None | Unset | UUID:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                owner_team_id_type_0 = UUID(data)

                return owner_team_id_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(None | Unset | UUID, data)

        owner_team_id = _parse_owner_team_id(d.pop("ownerTeamId", UNSET))

        acl_mode = d.pop("aclMode", UNSET)

        sensitivity = d.pop("sensitivity", UNSET)

        classification = d.pop("classification", UNSET)

        embedding_alias = d.pop("embeddingAlias", UNSET)

        text_search_config = d.pop("textSearchConfig", UNSET)

        def _parse_chunking(data: object) -> CollectionBodyChunkingType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                chunking_type_0 = CollectionBodyChunkingType0.from_dict(data)

                return chunking_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(CollectionBodyChunkingType0 | None | Unset, data)

        chunking = _parse_chunking(d.pop("chunking", UNSET))

        dims = d.pop("dims", UNSET)

        collection_body = cls(
            slug=slug,
            name=name,
            description=description,
            visibility=visibility,
            owner_team_id=owner_team_id,
            acl_mode=acl_mode,
            sensitivity=sensitivity,
            classification=classification,
            embedding_alias=embedding_alias,
            text_search_config=text_search_config,
            chunking=chunking,
            dims=dims,
        )

        return collection_body

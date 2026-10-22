from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast

if TYPE_CHECKING:
    from ..models.reindex_body_chunking_type_0 import ReindexBodyChunkingType0


T = TypeVar("T", bound="ReindexBody")


@_attrs_define
class ReindexBody:
    """
    Attributes:
        embedding_alias (None | str | Unset):
        chunking (None | ReindexBodyChunkingType0 | Unset):
        text_search_config (None | str | Unset):
        target_backend (None | str | Unset):
    """

    embedding_alias: None | str | Unset = UNSET
    chunking: None | ReindexBodyChunkingType0 | Unset = UNSET
    text_search_config: None | str | Unset = UNSET
    target_backend: None | str | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        from ..models.reindex_body_chunking_type_0 import ReindexBodyChunkingType0  # noqa: PLC0415

        embedding_alias: None | str | Unset
        if isinstance(self.embedding_alias, Unset):
            embedding_alias = UNSET
        else:
            embedding_alias = self.embedding_alias

        chunking: dict[str, Any] | None | Unset
        if isinstance(self.chunking, Unset):
            chunking = UNSET
        elif isinstance(self.chunking, ReindexBodyChunkingType0):
            chunking = self.chunking.to_dict()
        else:
            chunking = self.chunking

        text_search_config: None | str | Unset
        if isinstance(self.text_search_config, Unset):
            text_search_config = UNSET
        else:
            text_search_config = self.text_search_config

        target_backend: None | str | Unset
        if isinstance(self.target_backend, Unset):
            target_backend = UNSET
        else:
            target_backend = self.target_backend

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if embedding_alias is not UNSET:
            field_dict["embeddingAlias"] = embedding_alias
        if chunking is not UNSET:
            field_dict["chunking"] = chunking
        if text_search_config is not UNSET:
            field_dict["textSearchConfig"] = text_search_config
        if target_backend is not UNSET:
            field_dict["targetBackend"] = target_backend

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.reindex_body_chunking_type_0 import ReindexBodyChunkingType0  # noqa: PLC0415

        d = dict(src_dict)

        def _parse_embedding_alias(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        embedding_alias = _parse_embedding_alias(d.pop("embeddingAlias", UNSET))

        def _parse_chunking(data: object) -> None | ReindexBodyChunkingType0 | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                chunking_type_0 = ReindexBodyChunkingType0.from_dict(data)

                return chunking_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(None | ReindexBodyChunkingType0 | Unset, data)

        chunking = _parse_chunking(d.pop("chunking", UNSET))

        def _parse_text_search_config(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        text_search_config = _parse_text_search_config(d.pop("textSearchConfig", UNSET))

        def _parse_target_backend(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        target_backend = _parse_target_backend(d.pop("targetBackend", UNSET))

        reindex_body = cls(
            embedding_alias=embedding_alias,
            chunking=chunking,
            text_search_config=text_search_config,
            target_backend=target_backend,
        )

        return reindex_body

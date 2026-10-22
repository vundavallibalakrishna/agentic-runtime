from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast
from uuid import UUID


T = TypeVar("T", bound="SearchBody")


@_attrs_define
class SearchBody:
    """
    Attributes:
        query (str | Unset):  Default: ''.
        collection_ids (list[UUID] | Unset):
        top_k (int | Unset):  Default: 8.
        debug (bool | Unset):  Default: False.
    """

    query: str | Unset = ""
    collection_ids: list[UUID] | Unset = UNSET
    top_k: int | Unset = 8
    debug: bool | Unset = False

    def to_dict(self) -> dict[str, Any]:
        query = self.query

        collection_ids: list[str] | Unset = UNSET
        if not isinstance(self.collection_ids, Unset):
            collection_ids = []
            for collection_ids_item_data in self.collection_ids:
                collection_ids_item = str(collection_ids_item_data)
                collection_ids.append(collection_ids_item)

        top_k = self.top_k

        debug = self.debug

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if query is not UNSET:
            field_dict["query"] = query
        if collection_ids is not UNSET:
            field_dict["collectionIds"] = collection_ids
        if top_k is not UNSET:
            field_dict["topK"] = top_k
        if debug is not UNSET:
            field_dict["debug"] = debug

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        query = d.pop("query", UNSET)

        _collection_ids = d.pop("collectionIds", UNSET)
        collection_ids: list[UUID] | Unset = UNSET
        if _collection_ids is not UNSET:
            collection_ids = []
            for collection_ids_item_data in _collection_ids:
                collection_ids_item = UUID(collection_ids_item_data)

                collection_ids.append(collection_ids_item)

        top_k = d.pop("topK", UNSET)

        debug = d.pop("debug", UNSET)

        search_body = cls(
            query=query,
            collection_ids=collection_ids,
            top_k=top_k,
            debug=debug,
        )

        return search_body

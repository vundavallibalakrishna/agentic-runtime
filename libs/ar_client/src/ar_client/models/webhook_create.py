from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from typing import cast


T = TypeVar("T", bound="WebhookCreate")


@_attrs_define
class WebhookCreate:
    """
    Attributes:
        name (str):
        url (str):
        topics (list[str]):
    """

    name: str
    url: str
    topics: list[str]

    def to_dict(self) -> dict[str, Any]:
        name = self.name

        url = self.url

        topics = self.topics

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "name": name,
                "url": url,
                "topics": topics,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        name = d.pop("name")

        url = d.pop("url")

        topics = cast(list[str], d.pop("topics"))

        webhook_create = cls(
            name=name,
            url=url,
            topics=topics,
        )

        return webhook_create

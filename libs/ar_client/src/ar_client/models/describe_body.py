from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast


T = TypeVar("T", bound="DescribeBody")


@_attrs_define
class DescribeBody:
    """
    Attributes:
        description (str | Unset):  Default: ''.
        name (str | Unset):  Default: ''.
        slug (str | Unset):  Default: ''.
        method (str | Unset):  Default: ''.
        url (str | Unset):  Default: ''.
        connection (str | Unset):  Default: ''.
        parameters (list[str] | Unset):
        returns (str | Unset):  Default: ''.
        title (str | Unset):  Default: ''.
    """

    description: str | Unset = ""
    name: str | Unset = ""
    slug: str | Unset = ""
    method: str | Unset = ""
    url: str | Unset = ""
    connection: str | Unset = ""
    parameters: list[str] | Unset = UNSET
    returns: str | Unset = ""
    title: str | Unset = ""

    def to_dict(self) -> dict[str, Any]:
        description = self.description

        name = self.name

        slug = self.slug

        method = self.method

        url = self.url

        connection = self.connection

        parameters: list[str] | Unset = UNSET
        if not isinstance(self.parameters, Unset):
            parameters = self.parameters

        returns = self.returns

        title = self.title

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if description is not UNSET:
            field_dict["description"] = description
        if name is not UNSET:
            field_dict["name"] = name
        if slug is not UNSET:
            field_dict["slug"] = slug
        if method is not UNSET:
            field_dict["method"] = method
        if url is not UNSET:
            field_dict["url"] = url
        if connection is not UNSET:
            field_dict["connection"] = connection
        if parameters is not UNSET:
            field_dict["parameters"] = parameters
        if returns is not UNSET:
            field_dict["returns"] = returns
        if title is not UNSET:
            field_dict["title"] = title

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        description = d.pop("description", UNSET)

        name = d.pop("name", UNSET)

        slug = d.pop("slug", UNSET)

        method = d.pop("method", UNSET)

        url = d.pop("url", UNSET)

        connection = d.pop("connection", UNSET)

        parameters = cast(list[str], d.pop("parameters", UNSET))

        returns = d.pop("returns", UNSET)

        title = d.pop("title", UNSET)

        describe_body = cls(
            description=description,
            name=name,
            slug=slug,
            method=method,
            url=url,
            connection=connection,
            parameters=parameters,
            returns=returns,
            title=title,
        )

        return describe_body

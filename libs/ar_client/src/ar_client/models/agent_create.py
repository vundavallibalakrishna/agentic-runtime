from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast

if TYPE_CHECKING:
    from ..models.agent_create_definition_type_0 import AgentCreateDefinitionType0


T = TypeVar("T", bound="AgentCreate")


@_attrs_define
class AgentCreate:
    """
    Attributes:
        slug (str):
        name (str):
        description (str | Unset):  Default: ''.
        visibility (str | Unset):  Default: 'private'.
        risk_tier (str | Unset):  Default: 'low'.
        template (None | str | Unset):
        definition (AgentCreateDefinitionType0 | None | Unset):
    """

    slug: str
    name: str
    description: str | Unset = ""
    visibility: str | Unset = "private"
    risk_tier: str | Unset = "low"
    template: None | str | Unset = UNSET
    definition: AgentCreateDefinitionType0 | None | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        from ..models.agent_create_definition_type_0 import AgentCreateDefinitionType0  # noqa: PLC0415

        slug = self.slug

        name = self.name

        description = self.description

        visibility = self.visibility

        risk_tier = self.risk_tier

        template: None | str | Unset
        if isinstance(self.template, Unset):
            template = UNSET
        else:
            template = self.template

        definition: dict[str, Any] | None | Unset
        if isinstance(self.definition, Unset):
            definition = UNSET
        elif isinstance(self.definition, AgentCreateDefinitionType0):
            definition = self.definition.to_dict()
        else:
            definition = self.definition

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "slug": slug,
                "name": name,
            }
        )
        if description is not UNSET:
            field_dict["description"] = description
        if visibility is not UNSET:
            field_dict["visibility"] = visibility
        if risk_tier is not UNSET:
            field_dict["riskTier"] = risk_tier
        if template is not UNSET:
            field_dict["template"] = template
        if definition is not UNSET:
            field_dict["definition"] = definition

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.agent_create_definition_type_0 import AgentCreateDefinitionType0  # noqa: PLC0415

        d = dict(src_dict)
        slug = d.pop("slug")

        name = d.pop("name")

        description = d.pop("description", UNSET)

        visibility = d.pop("visibility", UNSET)

        risk_tier = d.pop("riskTier", UNSET)

        def _parse_template(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        template = _parse_template(d.pop("template", UNSET))

        def _parse_definition(data: object) -> AgentCreateDefinitionType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                definition_type_0 = AgentCreateDefinitionType0.from_dict(data)

                return definition_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(AgentCreateDefinitionType0 | None | Unset, data)

        definition = _parse_definition(d.pop("definition", UNSET))

        agent_create = cls(
            slug=slug,
            name=name,
            description=description,
            visibility=visibility,
            risk_tier=risk_tier,
            template=template,
            definition=definition,
        )

        return agent_create

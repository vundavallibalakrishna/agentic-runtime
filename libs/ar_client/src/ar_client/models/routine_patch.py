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
    from ..models.delivery_body import DeliveryBody
    from ..models.trigger_body import TriggerBody


T = TypeVar("T", bound="RoutinePatch")


@_attrs_define
class RoutinePatch:
    """
    Attributes:
        name (None | str | Unset):
        description (None | str | Unset):
        instructions (None | str | Unset):
        agent_id (None | Unset | UUID):
        trigger (None | TriggerBody | Unset):
        delivery (list[DeliveryBody] | None | Unset):
    """

    name: None | str | Unset = UNSET
    description: None | str | Unset = UNSET
    instructions: None | str | Unset = UNSET
    agent_id: None | Unset | UUID = UNSET
    trigger: None | TriggerBody | Unset = UNSET
    delivery: list[DeliveryBody] | None | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        from ..models.delivery_body import DeliveryBody  # noqa: PLC0415
        from ..models.trigger_body import TriggerBody  # noqa: PLC0415

        name: None | str | Unset
        if isinstance(self.name, Unset):
            name = UNSET
        else:
            name = self.name

        description: None | str | Unset
        if isinstance(self.description, Unset):
            description = UNSET
        else:
            description = self.description

        instructions: None | str | Unset
        if isinstance(self.instructions, Unset):
            instructions = UNSET
        else:
            instructions = self.instructions

        agent_id: None | str | Unset
        if isinstance(self.agent_id, Unset):
            agent_id = UNSET
        elif isinstance(self.agent_id, UUID):
            agent_id = str(self.agent_id)
        else:
            agent_id = self.agent_id

        trigger: dict[str, Any] | None | Unset
        if isinstance(self.trigger, Unset):
            trigger = UNSET
        elif isinstance(self.trigger, TriggerBody):
            trigger = self.trigger.to_dict()
        else:
            trigger = self.trigger

        delivery: list[dict[str, Any]] | None | Unset
        if isinstance(self.delivery, Unset):
            delivery = UNSET
        elif isinstance(self.delivery, list):
            delivery = []
            for delivery_type_0_item_data in self.delivery:
                delivery_type_0_item = delivery_type_0_item_data.to_dict()
                delivery.append(delivery_type_0_item)

        else:
            delivery = self.delivery

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if name is not UNSET:
            field_dict["name"] = name
        if description is not UNSET:
            field_dict["description"] = description
        if instructions is not UNSET:
            field_dict["instructions"] = instructions
        if agent_id is not UNSET:
            field_dict["agentId"] = agent_id
        if trigger is not UNSET:
            field_dict["trigger"] = trigger
        if delivery is not UNSET:
            field_dict["delivery"] = delivery

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.delivery_body import DeliveryBody  # noqa: PLC0415
        from ..models.trigger_body import TriggerBody  # noqa: PLC0415

        d = dict(src_dict)

        def _parse_name(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        name = _parse_name(d.pop("name", UNSET))

        def _parse_description(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        description = _parse_description(d.pop("description", UNSET))

        def _parse_instructions(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        instructions = _parse_instructions(d.pop("instructions", UNSET))

        def _parse_agent_id(data: object) -> None | Unset | UUID:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                agent_id_type_0 = UUID(data)

                return agent_id_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(None | Unset | UUID, data)

        agent_id = _parse_agent_id(d.pop("agentId", UNSET))

        def _parse_trigger(data: object) -> None | TriggerBody | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                trigger_type_0 = TriggerBody.from_dict(data)

                return trigger_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(None | TriggerBody | Unset, data)

        trigger = _parse_trigger(d.pop("trigger", UNSET))

        def _parse_delivery(data: object) -> list[DeliveryBody] | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                delivery_type_0 = []
                _delivery_type_0 = data
                for delivery_type_0_item_data in _delivery_type_0:
                    delivery_type_0_item = DeliveryBody.from_dict(delivery_type_0_item_data)

                    delivery_type_0.append(delivery_type_0_item)

                return delivery_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(list[DeliveryBody] | None | Unset, data)

        delivery = _parse_delivery(d.pop("delivery", UNSET))

        routine_patch = cls(
            name=name,
            description=description,
            instructions=instructions,
            agent_id=agent_id,
            trigger=trigger,
            delivery=delivery,
        )

        return routine_patch

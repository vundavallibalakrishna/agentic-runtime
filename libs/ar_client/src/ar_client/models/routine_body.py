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
    from ..models.routine_body_budget_type_0 import RoutineBodyBudgetType0
    from ..models.trigger_body import TriggerBody


T = TypeVar("T", bound="RoutineBody")


@_attrs_define
class RoutineBody:
    """
    Attributes:
        name (str):
        agent_id (UUID):
        instructions (str):
        trigger (TriggerBody):
        description (str | Unset):  Default: ''.
        agent_version_id (None | Unset | UUID):
        event_filter (None | str | Unset):
        delivery (list[DeliveryBody] | Unset):
        budget (None | RoutineBodyBudgetType0 | Unset):
        max_runs_per_day (int | None | Unset):
        concurrency_policy (None | str | Unset):
        run_as (None | str | Unset):
        service_account_id (None | Unset | UUID):
    """

    name: str
    agent_id: UUID
    instructions: str
    trigger: TriggerBody
    description: str | Unset = ""
    agent_version_id: None | Unset | UUID = UNSET
    event_filter: None | str | Unset = UNSET
    delivery: list[DeliveryBody] | Unset = UNSET
    budget: None | RoutineBodyBudgetType0 | Unset = UNSET
    max_runs_per_day: int | None | Unset = UNSET
    concurrency_policy: None | str | Unset = UNSET
    run_as: None | str | Unset = UNSET
    service_account_id: None | Unset | UUID = UNSET

    def to_dict(self) -> dict[str, Any]:
        from ..models.delivery_body import DeliveryBody  # noqa: PLC0415
        from ..models.routine_body_budget_type_0 import RoutineBodyBudgetType0  # noqa: PLC0415
        from ..models.trigger_body import TriggerBody  # noqa: PLC0415

        name = self.name

        agent_id = str(self.agent_id)

        instructions = self.instructions

        trigger = self.trigger.to_dict()

        description = self.description

        agent_version_id: None | str | Unset
        if isinstance(self.agent_version_id, Unset):
            agent_version_id = UNSET
        elif isinstance(self.agent_version_id, UUID):
            agent_version_id = str(self.agent_version_id)
        else:
            agent_version_id = self.agent_version_id

        event_filter: None | str | Unset
        if isinstance(self.event_filter, Unset):
            event_filter = UNSET
        else:
            event_filter = self.event_filter

        delivery: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.delivery, Unset):
            delivery = []
            for delivery_item_data in self.delivery:
                delivery_item = delivery_item_data.to_dict()
                delivery.append(delivery_item)

        budget: dict[str, Any] | None | Unset
        if isinstance(self.budget, Unset):
            budget = UNSET
        elif isinstance(self.budget, RoutineBodyBudgetType0):
            budget = self.budget.to_dict()
        else:
            budget = self.budget

        max_runs_per_day: int | None | Unset
        if isinstance(self.max_runs_per_day, Unset):
            max_runs_per_day = UNSET
        else:
            max_runs_per_day = self.max_runs_per_day

        concurrency_policy: None | str | Unset
        if isinstance(self.concurrency_policy, Unset):
            concurrency_policy = UNSET
        else:
            concurrency_policy = self.concurrency_policy

        run_as: None | str | Unset
        if isinstance(self.run_as, Unset):
            run_as = UNSET
        else:
            run_as = self.run_as

        service_account_id: None | str | Unset
        if isinstance(self.service_account_id, Unset):
            service_account_id = UNSET
        elif isinstance(self.service_account_id, UUID):
            service_account_id = str(self.service_account_id)
        else:
            service_account_id = self.service_account_id

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "name": name,
                "agentId": agent_id,
                "instructions": instructions,
                "trigger": trigger,
            }
        )
        if description is not UNSET:
            field_dict["description"] = description
        if agent_version_id is not UNSET:
            field_dict["agentVersionId"] = agent_version_id
        if event_filter is not UNSET:
            field_dict["eventFilter"] = event_filter
        if delivery is not UNSET:
            field_dict["delivery"] = delivery
        if budget is not UNSET:
            field_dict["budget"] = budget
        if max_runs_per_day is not UNSET:
            field_dict["maxRunsPerDay"] = max_runs_per_day
        if concurrency_policy is not UNSET:
            field_dict["concurrencyPolicy"] = concurrency_policy
        if run_as is not UNSET:
            field_dict["runAs"] = run_as
        if service_account_id is not UNSET:
            field_dict["serviceAccountId"] = service_account_id

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.delivery_body import DeliveryBody  # noqa: PLC0415
        from ..models.routine_body_budget_type_0 import RoutineBodyBudgetType0  # noqa: PLC0415
        from ..models.trigger_body import TriggerBody  # noqa: PLC0415

        d = dict(src_dict)
        name = d.pop("name")

        agent_id = UUID(d.pop("agentId"))

        instructions = d.pop("instructions")

        trigger = TriggerBody.from_dict(d.pop("trigger"))

        description = d.pop("description", UNSET)

        def _parse_agent_version_id(data: object) -> None | Unset | UUID:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                agent_version_id_type_0 = UUID(data)

                return agent_version_id_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(None | Unset | UUID, data)

        agent_version_id = _parse_agent_version_id(d.pop("agentVersionId", UNSET))

        def _parse_event_filter(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        event_filter = _parse_event_filter(d.pop("eventFilter", UNSET))

        _delivery = d.pop("delivery", UNSET)
        delivery: list[DeliveryBody] | Unset = UNSET
        if _delivery is not UNSET:
            delivery = []
            for delivery_item_data in _delivery:
                delivery_item = DeliveryBody.from_dict(delivery_item_data)

                delivery.append(delivery_item)

        def _parse_budget(data: object) -> None | RoutineBodyBudgetType0 | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                budget_type_0 = RoutineBodyBudgetType0.from_dict(data)

                return budget_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(None | RoutineBodyBudgetType0 | Unset, data)

        budget = _parse_budget(d.pop("budget", UNSET))

        def _parse_max_runs_per_day(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        max_runs_per_day = _parse_max_runs_per_day(d.pop("maxRunsPerDay", UNSET))

        def _parse_concurrency_policy(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        concurrency_policy = _parse_concurrency_policy(d.pop("concurrencyPolicy", UNSET))

        def _parse_run_as(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        run_as = _parse_run_as(d.pop("runAs", UNSET))

        def _parse_service_account_id(data: object) -> None | Unset | UUID:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                service_account_id_type_0 = UUID(data)

                return service_account_id_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(None | Unset | UUID, data)

        service_account_id = _parse_service_account_id(d.pop("serviceAccountId", UNSET))

        routine_body = cls(
            name=name,
            agent_id=agent_id,
            instructions=instructions,
            trigger=trigger,
            description=description,
            agent_version_id=agent_version_id,
            event_filter=event_filter,
            delivery=delivery,
            budget=budget,
            max_runs_per_day=max_runs_per_day,
            concurrency_policy=concurrency_policy,
            run_as=run_as,
            service_account_id=service_account_id,
        )

        return routine_body

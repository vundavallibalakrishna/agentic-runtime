from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast
from uuid import UUID


T = TypeVar("T", bound="EvalRunBody")


@_attrs_define
class EvalRunBody:
    """
    Attributes:
        agent_version_ref (str | Unset):  Default: 'published'.
        model_alias_override (None | str | Unset):
        baseline_eval_run_id (None | Unset | UUID):
        tags (list[str] | None | Unset):
        agent_id (None | Unset | UUID):
    """

    agent_version_ref: str | Unset = "published"
    model_alias_override: None | str | Unset = UNSET
    baseline_eval_run_id: None | Unset | UUID = UNSET
    tags: list[str] | None | Unset = UNSET
    agent_id: None | Unset | UUID = UNSET

    def to_dict(self) -> dict[str, Any]:
        agent_version_ref = self.agent_version_ref

        model_alias_override: None | str | Unset
        if isinstance(self.model_alias_override, Unset):
            model_alias_override = UNSET
        else:
            model_alias_override = self.model_alias_override

        baseline_eval_run_id: None | str | Unset
        if isinstance(self.baseline_eval_run_id, Unset):
            baseline_eval_run_id = UNSET
        elif isinstance(self.baseline_eval_run_id, UUID):
            baseline_eval_run_id = str(self.baseline_eval_run_id)
        else:
            baseline_eval_run_id = self.baseline_eval_run_id

        tags: list[str] | None | Unset
        if isinstance(self.tags, Unset):
            tags = UNSET
        elif isinstance(self.tags, list):
            tags = self.tags

        else:
            tags = self.tags

        agent_id: None | str | Unset
        if isinstance(self.agent_id, Unset):
            agent_id = UNSET
        elif isinstance(self.agent_id, UUID):
            agent_id = str(self.agent_id)
        else:
            agent_id = self.agent_id

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if agent_version_ref is not UNSET:
            field_dict["agentVersionRef"] = agent_version_ref
        if model_alias_override is not UNSET:
            field_dict["modelAliasOverride"] = model_alias_override
        if baseline_eval_run_id is not UNSET:
            field_dict["baselineEvalRunId"] = baseline_eval_run_id
        if tags is not UNSET:
            field_dict["tags"] = tags
        if agent_id is not UNSET:
            field_dict["agentId"] = agent_id

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        agent_version_ref = d.pop("agentVersionRef", UNSET)

        def _parse_model_alias_override(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        model_alias_override = _parse_model_alias_override(d.pop("modelAliasOverride", UNSET))

        def _parse_baseline_eval_run_id(data: object) -> None | Unset | UUID:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                baseline_eval_run_id_type_0 = UUID(data)

                return baseline_eval_run_id_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(None | Unset | UUID, data)

        baseline_eval_run_id = _parse_baseline_eval_run_id(d.pop("baselineEvalRunId", UNSET))

        def _parse_tags(data: object) -> list[str] | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                tags_type_0 = cast(list[str], data)

                return tags_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(list[str] | None | Unset, data)

        tags = _parse_tags(d.pop("tags", UNSET))

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

        eval_run_body = cls(
            agent_version_ref=agent_version_ref,
            model_alias_override=model_alias_override,
            baseline_eval_run_id=baseline_eval_run_id,
            tags=tags,
            agent_id=agent_id,
        )

        return eval_run_body

"""Every registered workflow must prepare under the real Temporal sandbox."""

import importlib
import pkgutil
from typing import get_origin

import pytest
from temporalio import workflow
from temporalio.converter import DataConverter
from temporalio.worker.workflow_sandbox import SandboxedWorkflowRunner


def _workflows() -> list[type]:
    found: list[type] = []
    for root in ("ar_runtime.workflows", "ar_system.workflows", "ar_ingest.workflows"):
        package = importlib.import_module(root)
        for item in pkgutil.iter_modules(package.__path__, root + "."):
            module = importlib.import_module(item.name)
            found.extend(
                value
                for value in vars(module).values()
                if (
                    isinstance(value, type)
                    and value.__module__ == item.name
                    and workflow._Definition.from_class(value) is not None
                )
            )
    return found


@pytest.mark.parametrize("workflow_type", _workflows(), ids=lambda value: value.__name__)
async def test_workflow_prepares_without_restricted_imports(workflow_type: type) -> None:
    definition = workflow._Definition.must_from_class(workflow_type)
    SandboxedWorkflowRunner().prepare_workflow(definition)


@pytest.mark.parametrize("workflow_type", _workflows(), ids=lambda value: value.__name__)
async def test_workflow_payload_types_accept_json_values(workflow_type: type) -> None:
    definition = workflow._Definition.must_from_class(workflow_type)
    if definition.arg_types and get_origin(definition.arg_types[0]) is dict:
        payload = {"id": "example", "count": 1, "enabled": True, "items": [{"value": None}]}
        converter = DataConverter.default
        encoded = await converter.encode([payload])
        assert await converter.decode(encoded, definition.arg_types) == [payload]
